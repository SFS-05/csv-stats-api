"""
Upload service — orchestrates file validation, storage, and job dispatch.
Enforces: MIME validation, extension validation, size limits, path safety.
"""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.exceptions import (
    FileTooLargeError,
    InvalidFileTypeError,
    InvalidMimeTypeError,
    MalformedFileError,
)
from backend.models.job import JobType
from backend.repositories.dataset_repo import DatasetRepository
from backend.repositories.job_repo import JobRepository
from backend.storage.base import generate_storage_key
from backend.storage.s3 import get_storage_backend


# ── MIME magic bytes for format verification ──────────────────────────────────
_MAGIC_BYTES: dict[str, list[bytes]] = {
    "parquet": [b"PAR1"],
    "xlsx": [b"PK\x03\x04"],  # ZIP-based
    "xls": [b"\xd0\xcf\x11\xe0"],  # OLE2
    "pdf": [b"%PDF"],  # Reject PDFs explicitly
}

_EXTENSION_TO_FORMAT: dict[str, str] = {
    ".csv": "csv",
    ".tsv": "tsv",
    ".xlsx": "xlsx",
    ".xls": "xls",
    ".json": "json",
    ".jsonl": "jsonl",
    ".parquet": "parquet",
}


def _detect_format(filename: str) -> str:
    """Derive file format from extension."""
    ext = Path(filename).suffix.lower()
    fmt = _EXTENSION_TO_FORMAT.get(ext)
    if not fmt:
        raise InvalidFileTypeError(
            f"Unsupported file extension: {ext!r}. "
            f"Allowed: {sorted(_EXTENSION_TO_FORMAT.keys())}"
        )
    return fmt


def _validate_mime(mime_type: str, file_format: str) -> None:
    """Validate MIME type is in the allowed set."""
    if mime_type not in settings.ALLOWED_MIME_TYPES:
        raise InvalidMimeTypeError(
            f"MIME type {mime_type!r} is not allowed for format {file_format!r}"
        )


def _check_magic_bytes(header: bytes, file_format: str) -> None:
    """Verify file magic bytes match the declared format."""
    if file_format in _MAGIC_BYTES:
        expected = _MAGIC_BYTES[file_format]
        if not any(header.startswith(magic) for magic in expected):
            raise MalformedFileError(
                f"File magic bytes do not match declared format {file_format!r}"
            )


class UploadService:
    """
    Handles the full upload pipeline:
    1. Validate file metadata (size, extension, MIME)
    2. Stream file to storage with SHA-256 checksum
    3. Create Dataset record
    4. Dispatch profiling job
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._storage = get_storage_backend()
        self._dataset_repo = DatasetRepository(session)
        self._job_repo = JobRepository(session)

    async def upload(
        self,
        file: UploadFile,
        owner_id: UUID,
        dataset_name: str | None = None,
    ) -> dict:
        """
        Validate, store, and enqueue a dataset file for profiling.
        Returns dataset and job metadata.
        """
        original_filename = file.filename or "unknown"
        content_type = file.content_type or "application/octet-stream"

        # ── Step 1: Extension validation ──────────────────────────────────────
        file_format = _detect_format(original_filename)

        # ── Step 2: MIME type validation ──────────────────────────────────────
        _validate_mime(content_type, file_format)

        # ── Step 3: Read file with size limit enforcement ─────────────────────
        max_bytes = settings.max_upload_bytes
        data = await self._read_with_limit(file, max_bytes)

        # ── Step 4: Magic bytes check ─────────────────────────────────────────
        _check_magic_bytes(data[:16], file_format)

        # ── Step 5: Compute checksum ──────────────────────────────────────────
        checksum = hashlib.sha256(data).hexdigest()

        # ── Step 6: Generate safe storage key ─────────────────────────────────
        storage_key = generate_storage_key(str(owner_id), original_filename)

        # ── Step 7: Persist to storage ────────────────────────────────────────
        await self._storage.put(
            key=storage_key,
            data=data,
            content_type=content_type,
        )
        logger.info(
            f"File stored: {storage_key!r}",
            size=len(data),
            format=file_format,
        )

        # ── Step 8: Create Dataset record ─────────────────────────────────────
        name = dataset_name or Path(original_filename).stem
        dataset = await self._dataset_repo.create(
            owner_id=owner_id,
            name=name,
            original_filename=original_filename,
            storage_key=storage_key,
            file_format=file_format,
            mime_type=content_type,
            file_size_bytes=len(data),
            checksum_sha256=checksum,
        )

        # ── Step 9: Create Job record ─────────────────────────────────────────
        job = await self._job_repo.create(
            dataset_id=dataset.id,
            owner_id=owner_id,
            job_type=JobType.PROFILING,
        )

        # ── Step 10: Dispatch Celery task ─────────────────────────────────────
        # Resolve the local file path for the worker
        local_path = str(settings.LOCAL_STORAGE_PATH / storage_key)

        from backend.workers.tasks.profiling import run_profiling
        task = run_profiling.apply_async(
            kwargs={
                "job_id": str(job.id),
                "dataset_id": str(dataset.id),
                "storage_key": storage_key,
                "file_format": file_format,
                "file_path": local_path,
            },
            task_id=str(job.id),
            queue="profiling",
        )

        logger.info(
            f"Profiling job dispatched: {task.id}",
            dataset_id=str(dataset.id),
            job_id=str(job.id),
        )

        return {
            "dataset_id": str(dataset.id),
            "job_id": str(job.id),
            "celery_task_id": task.id,
            "status": "queued",
            "file_format": file_format,
            "file_size_bytes": len(data),
            "checksum_sha256": checksum,
        }

    @staticmethod
    async def _read_with_limit(file: UploadFile, max_bytes: int) -> bytes:
        """
        Read upload stream with a hard size limit.
        Raises FileTooLargeError if the file exceeds max_bytes.
        """
        buffer = io.BytesIO()
        total = 0
        chunk_size = 65_536  # 64 KB chunks

        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise FileTooLargeError(
                    f"File exceeds maximum allowed size of "
                    f"{settings.MAX_UPLOAD_SIZE_MB} MB"
                )
            buffer.write(chunk)

        return buffer.getvalue()