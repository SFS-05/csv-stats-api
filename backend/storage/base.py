"""
Abstract storage backend interface.
Implementations: LocalStorageBackend, S3StorageBackend.
All paths are validated to prevent path traversal attacks.
"""
from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod
from pathlib import Path, PurePosixPath
from typing import AsyncIterator, BinaryIO
from uuid import uuid4

from backend.core.exceptions import PathTraversalError


# ── Path sanitization ─────────────────────────────────────────────────────────
_SAFE_KEY_RE = re.compile(r"^[a-zA-Z0-9_\-./]+$")


def sanitize_storage_key(key: str) -> str:
    """
    Validate and normalize a storage key.
    Raises PathTraversalError if the key contains traversal sequences.
    """
    normalized = key.replace("\\", "/")
    resolved = str(PurePosixPath(normalized))
    if resolved.startswith("/") or ".." in resolved.split("/"):
        raise PathTraversalError(f"Storage key contains path traversal: {key!r}")
    if not _SAFE_KEY_RE.match(resolved):
        raise PathTraversalError(f"Storage key contains invalid characters: {key!r}")
    return resolved


def generate_storage_key(owner_id: str, original_filename: str) -> str:
    """
    Generate a collision-resistant, safe storage key.
    Format: uploads/{owner_id}/{uuid}/{sanitized_filename}
    """
    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", Path(original_filename).name)
    safe_name = safe_name[:200]
    unique_id = str(uuid4())
    return f"uploads/{owner_id}/{unique_id}/{safe_name}"


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ── Abstract interface ────────────────────────────────────────────────────────
class StorageBackend(ABC):
    """Abstract storage backend. All methods are async."""

    @abstractmethod
    async def put(
        self,
        key: str,
        data: bytes | BinaryIO,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Store data and return the storage key."""
        ...

    @abstractmethod
    async def get(self, key: str) -> bytes:
        """Retrieve data by key."""
        ...

    @abstractmethod
    async def stream(
        self, key: str, chunk_size: int = 65_536
    ) -> AsyncIterator[bytes]:
        """Stream data in chunks to avoid loading entire file into memory."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete data by key."""
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a key exists."""
        ...

    @abstractmethod
    async def get_size(self, key: str) -> int:
        """Return the size in bytes of the stored object."""
        ...

    @abstractmethod
    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        """Return a (pre-signed) URL for the object."""
        ...