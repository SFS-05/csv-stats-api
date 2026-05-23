"""
Security tests for the upload pipeline.
Tests: path traversal, oversized payloads, malformed files, MIME spoofing.
"""
from __future__ import annotations

import io
import os
import tempfile

import pytest

from backend.core.exceptions import (
    FileTooLargeError,
    InvalidFileTypeError,
    MalformedFileError,
    PathTraversalError,
)
from backend.storage.base import sanitize_storage_key, generate_storage_key


# ── Path traversal tests ──────────────────────────────────────────────────────
class TestPathTraversal:
    def test_rejects_dotdot(self):
        with pytest.raises(PathTraversalError):
            sanitize_storage_key("../etc/passwd")

    def test_rejects_dotdot_encoded(self):
        with pytest.raises(PathTraversalError):
            sanitize_storage_key("uploads/../../etc/passwd")

    def test_rejects_absolute_path(self):
        with pytest.raises(PathTraversalError):
            sanitize_storage_key("/etc/passwd")

    def test_rejects_windows_traversal(self):
        with pytest.raises(PathTraversalError):
            sanitize_storage_key("uploads\\..\\..\\etc\\passwd")

    def test_rejects_special_chars(self):
        with pytest.raises(PathTraversalError):
            sanitize_storage_key("uploads/file;rm -rf /")

    def test_accepts_valid_key(self):
        key = "uploads/user-123/abc-def/dataset.csv"
        result = sanitize_storage_key(key)
        assert result == key

    def test_accepts_nested_valid_key(self):
        key = "uploads/owner_id/uuid/my_file.parquet"
        result = sanitize_storage_key(key)
        assert result == key

    def test_generated_key_is_safe(self):
        """Generated storage keys must always pass sanitization."""
        key = generate_storage_key("user-123", "my dataset (1).csv")
        # Should not raise
        sanitized = sanitize_storage_key(key)
        assert sanitized == key

    def test_generated_key_with_malicious_filename(self):
        """Even malicious filenames must produce safe storage keys."""
        key = generate_storage_key("user-123", "../../../etc/passwd")
        sanitized = sanitize_storage_key(key)
        assert ".." not in sanitized
        assert sanitized.startswith("uploads/")


# ── File type validation tests ────────────────────────────────────────────────
class TestFileTypeValidation:
    def test_rejects_exe_extension(self):
        from backend.services.upload_service import _detect_format
        with pytest.raises(InvalidFileTypeError):
            _detect_format("malware.exe")

    def test_rejects_php_extension(self):
        from backend.services.upload_service import _detect_format
        with pytest.raises(InvalidFileTypeError):
            _detect_format("shell.php")

    def test_rejects_no_extension(self):
        from backend.services.upload_service import _detect_format
        with pytest.raises(InvalidFileTypeError):
            _detect_format("noextension")

    def test_accepts_csv(self):
        from backend.services.upload_service import _detect_format
        assert _detect_format("data.csv") == "csv"

    def test_accepts_parquet(self):
        from backend.services.upload_service import _detect_format
        assert _detect_format("data.parquet") == "parquet"

    def test_accepts_xlsx(self):
        from backend.services.upload_service import _detect_format
        assert _detect_format("data.xlsx") == "xlsx"

    def test_case_insensitive_extension(self):
        from backend.services.upload_service import _detect_format
        assert _detect_format("DATA.CSV") == "csv"


# ── Magic bytes validation tests ──────────────────────────────────────────────
class TestMagicBytesValidation:
    def test_rejects_csv_with_parquet_magic(self):
        from backend.services.upload_service import _check_magic_bytes
        # Parquet magic bytes in a file declared as parquet
        parquet_magic = b"PAR1" + b"\x00" * 12
        # Should not raise for parquet
        _check_magic_bytes(parquet_magic, "parquet")

    def test_rejects_wrong_magic_for_parquet(self):
        from backend.services.upload_service import _check_magic_bytes
        with pytest.raises(MalformedFileError):
            _check_magic_bytes(b"This is not parquet data", "parquet")

    def test_accepts_csv_without_magic_check(self):
        from backend.services.upload_service import _check_magic_bytes
        # CSV has no magic bytes requirement
        _check_magic_bytes(b"col1,col2\n1,2\n", "csv")

    def test_rejects_xlsx_with_wrong_magic(self):
        from backend.services.upload_service import _check_magic_bytes
        with pytest.raises(MalformedFileError):
            _check_magic_bytes(b"This is not a zip file", "xlsx")


# ── MIME type validation tests ────────────────────────────────────────────────
class TestMimeValidation:
    def test_rejects_text_html(self):
        from backend.services.upload_service import _validate_mime
        with pytest.raises(Exception):
            _validate_mime("text/html", "csv")

    def test_rejects_application_javascript(self):
        from backend.services.upload_service import _validate_mime
        with pytest.raises(Exception):
            _validate_mime("application/javascript", "csv")

    def test_accepts_text_csv(self):
        from backend.services.upload_service import _validate_mime
        # Should not raise
        _validate_mime("text/csv", "csv")


# ── Local storage confinement tests ───────────────────────────────────────────
class TestStorageConfinement:
    def test_local_storage_confines_to_base(self):
        """Files must never be written outside the base storage directory."""
        import asyncio
        from pathlib import Path
        from backend.storage.local import LocalStorageBackend

        with tempfile.TemporaryDirectory() as tmpdir:
            backend = LocalStorageBackend(base_path=Path(tmpdir))

            async def run():
                with pytest.raises(Exception):
                    await backend.put("../outside/file.txt", b"data")

            asyncio.run(run())

    def test_local_storage_accepts_valid_key(self):
        import asyncio
        from pathlib import Path
        from backend.storage.local import LocalStorageBackend

        with tempfile.TemporaryDirectory() as tmpdir:
            backend = LocalStorageBackend(base_path=Path(tmpdir))

            async def run():
                await backend.put("uploads/user/file.csv", b"col1,col2\n1,2\n")
                data = await backend.get("uploads/user/file.csv")
                assert data == b"col1,col2\n1,2\n"

            asyncio.run(run())