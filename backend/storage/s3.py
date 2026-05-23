"""
S3-compatible storage backend using aioboto3.
Works with AWS S3, MinIO, Cloudflare R2, and any S3-compatible service.
"""
from __future__ import annotations

from typing import AsyncIterator, BinaryIO

from backend.core.config import settings
from backend.core.exceptions import StorageError
from backend.storage.base import StorageBackend, sanitize_storage_key


class S3StorageBackend(StorageBackend):
    """
    S3-compatible object storage backend.
    Uses aioboto3 for fully async operations.
    """

    def __init__(self) -> None:
        self._bucket = settings.S3_BUCKET_NAME
        self._endpoint = settings.S3_ENDPOINT_URL
        self._region = settings.S3_REGION
        self._access_key = settings.S3_ACCESS_KEY_ID
        self._secret_key = settings.S3_SECRET_ACCESS_KEY
        self._session = None

    def _get_session(self):
        """Lazy-initialize aioboto3 session."""
        try:
            import aioboto3
        except ImportError:
            raise StorageError(
                "aioboto3 is required for S3 storage. Install it with: pip install aioboto3"
            )
        if self._session is None:
            self._session = aioboto3.Session(
                aws_access_key_id=self._access_key,
                aws_secret_access_key=self._secret_key,
                region_name=self._region,
            )
        return self._session

    def _client_kwargs(self) -> dict:
        kwargs: dict = {}
        if self._endpoint:
            kwargs["endpoint_url"] = self._endpoint
        return kwargs

    async def put(
        self,
        key: str,
        data: bytes | BinaryIO,
        content_type: str = "application/octet-stream",
    ) -> str:
        safe_key = sanitize_storage_key(key)
        session = self._get_session()
        try:
            async with session.client("s3", **self._client_kwargs()) as s3:
                if isinstance(data, bytes):
                    await s3.put_object(
                        Bucket=self._bucket,
                        Key=safe_key,
                        Body=data,
                        ContentType=content_type,
                    )
                else:
                    await s3.upload_fileobj(
                        data,
                        self._bucket,
                        safe_key,
                        ExtraArgs={"ContentType": content_type},
                    )
        except Exception as exc:
            raise StorageError(f"S3 put failed for {safe_key!r}: {exc}") from exc
        return safe_key

    async def get(self, key: str) -> bytes:
        safe_key = sanitize_storage_key(key)
        session = self._get_session()
        try:
            async with session.client("s3", **self._client_kwargs()) as s3:
                response = await s3.get_object(Bucket=self._bucket, Key=safe_key)
                return await response["Body"].read()
        except Exception as exc:
            raise StorageError(f"S3 get failed for {safe_key!r}: {exc}") from exc

    async def stream(
        self, key: str, chunk_size: int = 65_536
    ) -> AsyncIterator[bytes]:
        safe_key = sanitize_storage_key(key)
        session = self._get_session()
        try:
            async with session.client("s3", **self._client_kwargs()) as s3:
                response = await s3.get_object(Bucket=self._bucket, Key=safe_key)
                async for chunk in response["Body"].iter_chunks(chunk_size):
                    yield chunk
        except Exception as exc:
            raise StorageError(f"S3 stream failed for {safe_key!r}: {exc}") from exc

    async def delete(self, key: str) -> None:
        safe_key = sanitize_storage_key(key)
        session = self._get_session()
        try:
            async with session.client("s3", **self._client_kwargs()) as s3:
                await s3.delete_object(Bucket=self._bucket, Key=safe_key)
        except Exception as exc:
            raise StorageError(f"S3 delete failed for {safe_key!r}: {exc}") from exc

    async def exists(self, key: str) -> bool:
        safe_key = sanitize_storage_key(key)
        session = self._get_session()
        try:
            async with session.client("s3", **self._client_kwargs()) as s3:
                await s3.head_object(Bucket=self._bucket, Key=safe_key)
                return True
        except Exception:
            return False

    async def get_size(self, key: str) -> int:
        safe_key = sanitize_storage_key(key)
        session = self._get_session()
        try:
            async with session.client("s3", **self._client_kwargs()) as s3:
                response = await s3.head_object(Bucket=self._bucket, Key=safe_key)
                return response["ContentLength"]
        except Exception as exc:
            raise StorageError(f"S3 head failed for {safe_key!r}: {exc}") from exc

    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        safe_key = sanitize_storage_key(key)
        session = self._get_session()
        try:
            async with session.client("s3", **self._client_kwargs()) as s3:
                return await s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self._bucket, "Key": safe_key},
                    ExpiresIn=expires_in,
                )
        except Exception as exc:
            raise StorageError(f"S3 presign failed for {safe_key!r}: {exc}") from exc


def get_storage_backend() -> StorageBackend:
    """Factory: return the configured storage backend."""
    if settings.STORAGE_BACKEND == "s3":
        return S3StorageBackend()
    from backend.storage.local import LocalStorageBackend
    return LocalStorageBackend()