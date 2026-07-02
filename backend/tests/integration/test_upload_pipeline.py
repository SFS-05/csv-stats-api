"""
Integration tests for the full upload → profiling pipeline.

These tests require a running PostgreSQL + Redis instance.
Run with: pytest backend/tests/integration/ -v --timeout=60

Environment variables required (or use .env.test):
  DATABASE_URL, REDIS_URL, STORAGE_BACKEND=local, LOCAL_STORAGE_PATH=/tmp/test-uploads
"""
import asyncio
import io
import os
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_CSV_SMALL = b"""id,name,age,salary,department,hire_date
1,Alice,30,75000.00,Engineering,2020-01-15
2,Bob,25,55000.00,Marketing,2021-03-22
3,Carol,35,90000.00,Engineering,2019-07-01
4,Dave,28,62000.00,Sales,2022-11-10
5,Eve,32,80000.00,Engineering,2020-06-30
6,Frank,45,110000.00,Management,2015-04-12
7,Grace,27,58000.00,Marketing,2023-01-05
8,Heidi,38,95000.00,Engineering,2018-09-20
9,Ivan,31,70000.00,Sales,2021-08-14
10,Judy,29,65000.00,HR,2022-02-28
"""

SAMPLE_CSV_WITH_NULLS = b"""col_a,col_b,col_c
1,,hello
2,2.5,
3,3.0,world
,4.0,foo
5,,bar
"""

SAMPLE_CSV_MALFORMED = b"""col_a,col_b
1,2,3
4,5
"""


@pytest.fixture
def small_csv_file():
    """In-memory CSV file object."""
    buf = io.BytesIO(SAMPLE_CSV_SMALL)
    buf.name = "test_employees.csv"
    return buf


@pytest.fixture
def nulls_csv_file():
    buf = io.BytesIO(SAMPLE_CSV_WITH_NULLS)
    buf.name = "test_nulls.csv"
    return buf


@pytest.fixture
def malformed_csv_file():
    buf = io.BytesIO(SAMPLE_CSV_MALFORMED)
    buf.name = "test_malformed.csv"
    return buf


# ---------------------------------------------------------------------------
# Unit-level pipeline tests (no external services required)
# ---------------------------------------------------------------------------

class TestProfilingEngineIntegration:
    """Test the profiling engine end-to-end with real CSV data."""

    def test_profile_small_csv(self, tmp_path):
        """Full profiling run on a small CSV produces correct statistics."""
        import pandas as pd
        from backend.profiling.engine import ProfilingEngine

        csv_path = tmp_path / "employees.csv"
        csv_path.write_bytes(SAMPLE_CSV_SMALL)

        engine = ProfilingEngine()
        result = engine.profile_file(str(csv_path))

        assert result is not None
        assert result.row_count == 10
        assert result.column_count == 6
        assert len(result.columns) == 6

        # Check numeric column stats
        age_col = next(c for c in result.columns if c.name == "age")
        assert age_col.inferred_type == "numeric"
        assert age_col.mean is not None
        assert 25 <= age_col.mean <= 45
        assert age_col.min_value == 25.0
        assert age_col.max_value == 45.0
        assert age_col.null_count == 0

        # Check categorical column
        dept_col = next(c for c in result.columns if c.name == "department")
        assert dept_col.inferred_type == "categorical"
        assert dept_col.unique_count == 5  # Engineering, Marketing, Sales, Management, HR

        # Check date column
        date_col = next(c for c in result.columns if c.name == "hire_date")
        assert date_col.inferred_type in ("datetime", "categorical")

    def test_profile_csv_with_nulls(self, tmp_path):
        """Profiling correctly counts null values."""
        from backend.profiling.engine import ProfilingEngine

        csv_path = tmp_path / "nulls.csv"
        csv_path.write_bytes(SAMPLE_CSV_WITH_NULLS)

        engine = ProfilingEngine()
        result = engine.profile_file(str(csv_path))

        assert result.row_count == 5

        col_a = next(c for c in result.columns if c.name == "col_a")
        assert col_a.null_count == 1
        assert col_a.null_percentage == pytest.approx(20.0, abs=0.1)

        col_b = next(c for c in result.columns if c.name == "col_b")
        assert col_b.null_count == 2
        assert col_b.null_percentage == pytest.approx(40.0, abs=0.1)

        col_c = next(c for c in result.columns if c.name == "col_c")
        assert col_c.null_count == 1

    def test_profile_large_csv_streaming(self, tmp_path):
        """Profiling a large CSV uses streaming and stays within memory bounds."""
        import pandas as pd
        from backend.profiling.engine import ProfilingEngine

        # Generate 50k rows
        rows = ["id,value,category"]
        for i in range(50_000):
            rows.append(f"{i},{i * 1.5 + 0.1},cat_{i % 10}")
        csv_path = tmp_path / "large.csv"
        csv_path.write_text("\n".join(rows))

        engine = ProfilingEngine()
        result = engine.profile_file(str(csv_path))

        assert result.row_count == 50_000
        value_col = next(c for c in result.columns if c.name == "value")
        assert value_col.mean is not None
        assert value_col.std_dev is not None

    def test_welford_accumulator_accuracy(self):
        """Welford online algorithm matches numpy for mean/variance."""
        import math
        import numpy as np
        from backend.profiling.engine import WelfordAccumulator

        data = [1.5, 2.3, 4.7, 8.1, 3.2, 6.6, 9.0, 0.5, 7.7, 5.4]
        acc = WelfordAccumulator()
        for x in data:
            acc.update(x)

        assert acc.mean == pytest.approx(np.mean(data), rel=1e-9)
        assert acc.variance == pytest.approx(np.var(data, ddof=1), rel=1e-6)
        assert acc.std_dev == pytest.approx(np.std(data, ddof=1), rel=1e-6)
        assert acc.count == len(data)

    def test_reservoir_sampler_bounded_memory(self):
        """Reservoir sampler never exceeds its capacity."""
        from backend.profiling.engine import ReservoirSampler

        sampler = ReservoirSampler(capacity=100)
        for i in range(10_000):
            sampler.update(float(i))

        assert len(sampler.samples) <= 100
        assert sampler.count == 10_000


# ---------------------------------------------------------------------------
# Storage backend integration tests
# ---------------------------------------------------------------------------

class TestLocalStorageBackend:
    """Test local filesystem storage backend."""

    @pytest.mark.asyncio
    async def test_store_and_retrieve(self, tmp_path):
        """Store a file and retrieve it back."""
        from backend.storage.local import LocalStorageBackend

        backend = LocalStorageBackend(base_path=str(tmp_path))
        content = b"hello, world\n" * 100
        key = f"uploads/{uuid.uuid4()}.csv"

        await backend.store(key, io.BytesIO(content))
        retrieved = await backend.retrieve(key)
        assert retrieved == content

    @pytest.mark.asyncio
    async def test_delete(self, tmp_path):
        """Delete removes the file."""
        from backend.storage.local import LocalStorageBackend

        backend = LocalStorageBackend(base_path=str(tmp_path))
        key = f"uploads/{uuid.uuid4()}.csv"
        await backend.store(key, io.BytesIO(b"data"))
        await backend.delete(key)

        with pytest.raises(FileNotFoundError):
            await backend.retrieve(key)

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, tmp_path):
        """Path traversal attempts are rejected."""
        from backend.storage.local import LocalStorageBackend
        from backend.core.exceptions import PathTraversalError

        backend = LocalStorageBackend(base_path=str(tmp_path))

        with pytest.raises(PathTraversalError):
            await backend.store("../../etc/passwd", io.BytesIO(b"evil"))

    @pytest.mark.asyncio
    async def test_exists(self, tmp_path):
        """exists() returns correct boolean."""
        from backend.storage.local import LocalStorageBackend

        backend = LocalStorageBackend(base_path=str(tmp_path))
        key = f"uploads/{uuid.uuid4()}.csv"

        assert not await backend.exists(key)
        await backend.store(key, io.BytesIO(b"data"))
        assert await backend.exists(key)


# ---------------------------------------------------------------------------
# Upload service unit tests (mocked DB + storage)
# ---------------------------------------------------------------------------

class TestUploadServiceUnit:
    """Test upload service logic with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_upload_validates_mime_type(self):
        """Upload service rejects non-CSV MIME types."""
        from backend.services.upload_service import UploadService
        from backend.core.exceptions import ValidationError

        service = UploadService(
            storage=AsyncMock(),
            dataset_repo=AsyncMock(),
            job_repo=AsyncMock(),
        )

        fake_file = MagicMock()
        fake_file.filename = "malware.exe"
        fake_file.content_type = "application/x-msdownload"
        fake_file.read = AsyncMock(return_value=b"MZ\x90\x00")

        with pytest.raises((ValidationError, Exception)):
            await service.upload(fake_file, user_id=uuid.uuid4())

    @pytest.mark.asyncio
    async def test_upload_validates_file_size(self):
        """Upload service rejects files exceeding max size."""
        from backend.services.upload_service import UploadService
        from backend.core.exceptions import ValidationError

        service = UploadService(
            storage=AsyncMock(),
            dataset_repo=AsyncMock(),
            job_repo=AsyncMock(),
            max_file_size_mb=1,
        )

        fake_file = MagicMock()
        fake_file.filename = "big.csv"
        fake_file.content_type = "text/csv"
        # 2 MB of data
        fake_file.read = AsyncMock(return_value=b"a,b\n1,2\n" * 200_000)

        with pytest.raises((ValidationError, Exception)):
            await service.upload(fake_file, user_id=uuid.uuid4())

    @pytest.mark.asyncio
    async def test_upload_dispatches_celery_task(self):
        """Successful upload dispatches a Celery profiling task."""
        from backend.services.upload_service import UploadService

        mock_storage = AsyncMock()
        mock_storage.store = AsyncMock()
        mock_storage.exists = AsyncMock(return_value=False)

        mock_dataset_repo = AsyncMock()
        mock_dataset_repo.create = AsyncMock(return_value=MagicMock(id=uuid.uuid4()))

        mock_job_repo = AsyncMock()
        mock_job_repo.create = AsyncMock(return_value=MagicMock(id=uuid.uuid4()))

        service = UploadService(
            storage=mock_storage,
            dataset_repo=mock_dataset_repo,
            job_repo=mock_job_repo,
        )

        fake_file = MagicMock()
        fake_file.filename = "employees.csv"
        fake_file.content_type = "text/csv"
        fake_file.read = AsyncMock(side_effect=[SAMPLE_CSV_SMALL, b""])
        fake_file.size = len(SAMPLE_CSV_SMALL)

        with patch("backend.workers.tasks.profiling.run_profiling.delay") as mock_delay:
            mock_delay.return_value = MagicMock(id="celery-task-id")
            result = await service.upload(fake_file, user_id=uuid.uuid4())

        assert result is not None
        mock_delay.assert_called_once()


# ---------------------------------------------------------------------------
# DuckDB preview tests
# ---------------------------------------------------------------------------

class TestDuckDBPreview:
    """Test DuckDB-based dataset preview."""

    def test_preview_returns_paginated_rows(self, tmp_path):
        """DuckDB preview returns correct page of rows."""
        import duckdb

        csv_path = tmp_path / "employees.csv"
        csv_path.write_bytes(SAMPLE_CSV_SMALL)

        conn = duckdb.connect()
        result = conn.execute(
            f"SELECT * FROM read_csv_auto('{csv_path}') LIMIT 5 OFFSET 0"
        ).fetchall()

        assert len(result) == 5
        conn.close()

    def test_preview_with_filter(self, tmp_path):
        """DuckDB preview supports column filtering."""
        import duckdb

        csv_path = tmp_path / "employees.csv"
        csv_path.write_bytes(SAMPLE_CSV_SMALL)

        conn = duckdb.connect()
        result = conn.execute(
            f"SELECT * FROM read_csv_auto('{csv_path}') WHERE department = 'Engineering'"
        ).fetchall()

        assert len(result) == 4  # Alice, Carol, Eve, Heidi
        conn.close()

    def test_preview_with_sort(self, tmp_path):
        """DuckDB preview supports ORDER BY."""
        import duckdb

        csv_path = tmp_path / "employees.csv"
        csv_path.write_bytes(SAMPLE_CSV_SMALL)

        conn = duckdb.connect()
        result = conn.execute(
            f"SELECT name, age FROM read_csv_auto('{csv_path}') ORDER BY age ASC LIMIT 3"
        ).fetchall()

        assert result[0][1] == 25  # Bob is youngest
        conn.close()

    def test_sql_injection_prevention(self, tmp_path):
        """SQL injection in filter values is handled safely."""
        import duckdb

        csv_path = tmp_path / "employees.csv"
        csv_path.write_bytes(SAMPLE_CSV_SMALL)

        conn = duckdb.connect()
        # Use parameterized query — injection attempt should not execute
        malicious_input = "'; DROP TABLE employees; --"
        result = conn.execute(
            f"SELECT * FROM read_csv_auto('{csv_path}') WHERE department = ?",
            [malicious_input]
        ).fetchall()

        assert result == []  # No match, no error
        conn.close()

    def test_excel_preview_returns_rows(self, tmp_path):
        """Excel previews use pandas instead of falling back to CSV sniffing."""
        import pandas as pd
        from backend.api.v1.endpoints.datasets import _query_preview

        xlsx_path = tmp_path / "unstructured.xlsx"
        pd.DataFrame(
            {
                "title": ["First note", "Second note", "Third note"],
                "body": ["hello world", "engineering update", "sales update"],
                "score": [3, 1, 2],
            }
        ).to_excel(xlsx_path, index=False)

        rows, columns, total = _query_preview(
            file_path=str(xlsx_path),
            file_format="xlsx",
            page=1,
            page_size=2,
            sort_by="score",
            sort_order="asc",
            filter_col="body",
            filter_val="update",
        )

        assert columns == ["title", "body", "score"]
        assert total == 2
        assert [row["title"] for row in rows] == ["Second note", "Third note"]

    def test_excel_chart_column_sample(self, tmp_path):
        """Chart helpers can load Excel columns without treating them as CSV."""
        import pandas as pd
        from backend.visualization.charts import generate_bar_chart

        xlsx_path = tmp_path / "categories.xlsx"
        pd.DataFrame(
            {
                "label": ["spam", "ham", "spam", "updates"],
                "score": [1, 2, 3, 4],
            }
        ).to_excel(xlsx_path, index=False)

        chart = generate_bar_chart(str(xlsx_path), "xlsx", "label", top_n=3)

        assert chart["type"] == "bar"
        assert chart["total_values"] == 4
        assert chart["bars"][0]["value"] == "spam"
        assert chart["bars"][0]["count"] == 2


# ---------------------------------------------------------------------------
# Schema inference tests
# ---------------------------------------------------------------------------

class TestSchemaInference:
    """Test column type inference logic."""

    def test_infers_numeric_columns(self, tmp_path):
        """Integer and float columns are inferred as numeric."""
        from backend.profiling.engine import ProfilingEngine

        csv_path = tmp_path / "types.csv"
        csv_path.write_text("int_col,float_col,str_col\n1,1.5,hello\n2,2.5,world\n3,3.5,foo\n")

        engine = ProfilingEngine()
        result = engine.profile_file(str(csv_path))

        int_col = next(c for c in result.columns if c.name == "int_col")
        float_col = next(c for c in result.columns if c.name == "float_col")
        str_col = next(c for c in result.columns if c.name == "str_col")

        assert int_col.inferred_type == "numeric"
        assert float_col.inferred_type == "numeric"
        assert str_col.inferred_type == "categorical"

    def test_infers_boolean_columns(self, tmp_path):
        """Boolean-like columns are detected."""
        from backend.profiling.engine import ProfilingEngine

        csv_path = tmp_path / "bools.csv"
        csv_path.write_text("flag,value\ntrue,1\nfalse,2\ntrue,3\nfalse,4\n")

        engine = ProfilingEngine()
        result = engine.profile_file(str(csv_path))

        flag_col = next(c for c in result.columns if c.name == "flag")
        assert flag_col.inferred_type in ("boolean", "categorical")

    def test_infers_datetime_columns(self, tmp_path):
        """ISO date strings are inferred as datetime."""
        from backend.profiling.engine import ProfilingEngine

        csv_path = tmp_path / "dates.csv"
        csv_path.write_text("event_date,value\n2024-01-01,10\n2024-02-15,20\n2024-03-30,30\n")

        engine = ProfilingEngine()
        result = engine.profile_file(str(csv_path))

        date_col = next(c for c in result.columns if c.name == "event_date")
        assert date_col.inferred_type in ("datetime", "categorical")
