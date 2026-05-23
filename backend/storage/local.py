"""
Local filesystem storage backend.
Used for development and single-node deployments.
Files are stored under a configurable base directory with strict path validation.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import AsyncIterator, BinaryIO

import aiofiles
import aiofiles.os

from backend.core.config import settings
from backend.core.exceptions import StorageError
from backend.storage.base import StorageBackend, sanitize_storage_key


class LocalStorageBackend(StorageBackend):
    """
    Stores files on the local filesystem under settings.LOCAL_STORAGE_PATH.
    All keys are validated and resolved relative to the base directory.
    """

    def __init__(self, base_path: Path | None = None) -> None:
        self._base = (base_path or settings.LOCAL_STORAGE_PATH).resolve()
        self._base.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        """Resolve a storage key to an absolute path, enforcing base confinement."""
        safe_key = sanitize_storage_key(key)
        full_path = (self._base / safe_key).resolve()
        if not str(full_path).startswith(str(self._base)):
            from backend.core.exceptions import PathTraversalError
            raise PathTraversalError(f"Resolved path escapes storage root: {key!r}")
        return full_path

    async def put(
        self,
        key: str,
        data: bytes | BinaryIO,
        content_type: str = "application/octet-stream",
    ) -> str:
        path = self._resolve(key)
        try:
            await aiofiles.os.makedirs(str(path.parent), exist_ok=True)
            if isinstance(data, bytes):
                async with aiofiles.open(path, "wb") as f:
                    await f.write(data)
            else:
                async with aiofiles.open(path, "wb") as f:
                    loop = asyncio.get_event_loop()
                    chunk = await loop.run_in_executor(None, data.read, 65_536)
                    while chunk:
                        await f.write(chunk)
                        chunk = await loop.run_in_executor(None, data.read, 65_536)
        except OSError as exc:
            raise StorageError(f"Failed to write {key!r}: {exc}") from exc
        return key

    async def get(self, key: str) -> bytes:
        path = self._resolve(key)
        try:
            async with aiofiles.open(path, "rb") as f:
                return await f.read()
        except FileNotFoundError:
            raise StorageError(f"Object not found: {key!r}")
        except OSError as exc:
            raise StorageError(f"Failed to read {key!r}: {exc}") from exc

    async def stream(
        self, key: str, chunk_size: int = 65_536
    ) -> AsyncIterator[bytes]:
        path = self._resolve(key)
        try:
            async with aiofiles.open(path, "rb") as f:
                while True:
                    chunk = await f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
        except FileNotFoundError:
            raise StorageError(f"Object not found: {key!r}")
        except OSError as exc:
            raise StorageError(f"Failed to stream {key!r}: {exc}") from exc

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        try:
            await aiofiles.os.remove(str(path))
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise StorageError(f"Failed to delete {key!r}: {exc}") from exc

    async def exists(self, key: str) -> bool:
        path = self._resolve(key)
        return path.exists()

    async def get_size(self, key: str) -> int:
        path = self._resolve(key)
        try:
            stat = await aiofiles.os.stat(str(path))
            return stat.st_size
        except FileNotFoundError:
            raise StorageError(f"Object not found: {key!r}")

    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        safe_key = sanitize_storage_key(key)
        return f"/api/v1/storage/{safe_key}"