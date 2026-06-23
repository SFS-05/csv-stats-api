"""
Celery tasks for dataset profiling.
Runs in a separate worker process to avoid blocking the FastAPI event loop.
Implements: progress tracking, retries, cancellation, timeout handling.
"""
from __future__ import annotations

import traceback
from datetime import date, datetime, timezone
from math import isfinite
from typing import Any
from uuid import UUID

import numpy as np
import pandas as pd
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import settings
from backend.core.exceptions import MalformedFileError, ProfilingError
from backend.models.dataset import Dataset, DatasetStatus
from backend.models.job import Job, JobStatus
from backend.profiling.engine import ProfilingEngine
from backend.workers.celery_app import celery_app


def _to_json_safe(value: Any) -> Any:
    """Convert pandas/numpy objects into values PostgreSQL JSONB can store."""
    if value is None:
        return None
    if isinstance(value, dict):
        return {str(k): _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_json_safe(v) for v in value]
    if isinstance(value, np.generic):
        return _to_json_safe(value.item())
    if isinstance(value, np.ndarray):
        return [_to_json_safe(v) for v in value.tolist()]
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value.isoformat()
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, float):
        return value if isfinite(value) else None
    return value


def _schema_from_profiles(column_profiles: list[dict[str, Any]]) -> dict[str, Any]:
    columns = []
    for profile in column_profiles:
        inferred_type = profile.get("inferred_type") or "categorical"
        top_values = (profile.get("categorical_stats") or {}).get("top_values", [])
        sample_values = [
            item.get("value")
            for item in top_values
            if isinstance(item, dict) and "value" in item
        ][:5]
        columns.append(
            {
                "name": profile.get("column_name", ""),
                "dtype": inferred_type,
                "inferred_type": inferred_type,
                "nullable": int(profile.get("null_count") or 0) > 0,
                "null_count": int(profile.get("null_count") or 0),
                "null_pct": float(profile.get("null_pct") or 0.0),
                "unique_count": profile.get("unique_count"),
                "sample_values": sample_values,
            }
        )
    return {"columns": columns}


# ── Synchronous DB session for Celery workers ─────────────────────────────────
def _get_sync_session() -> Session:
    engine = create_engine(
        settings.DATABASE_URL_SYNC,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return SessionLocal()


class BaseTask(Task):
    """Base task class with DB session lifecycle management."""
    abstract = True
    _session: Session | None = None

    @property
    def session(self) -> Session:
        if self._session is None:
            self._session = _get_sync_session()
        return self._session

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        if self._session:
            self._session.close()
            self._session = None


@celery_app.task(
    bind=True,
    base=BaseTask,
    name="backend.workers.tasks.profiling.run_profiling",
    queue="profiling",
    max_retries=3,
    default_retry_delay=30,
    soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
    time_limit=settings.CELERY_TASK_TIME_LIMIT,
    acks_late=True,
)
def run_profiling(
    self: BaseTask,
    job_id: str,
    dataset_id: str,
    storage_key: str,
    file_format: str,
    file_path: str,
) -> dict:
    """
    Profile a dataset file and persist results to PostgreSQL.

    Args:
        job_id: UUID of the Job record to update
        dataset_id: UUID of the Dataset record to update
        storage_key: Storage key for the uploaded file
        file_format: File format string (csv, parquet, etc.)
        file_path: Absolute path to the file on the worker filesystem
    """
    session = self.session
    job: Job | None = session.get(Job, UUID(job_id))
    dataset: Dataset | None = session.get(Dataset, UUID(dataset_id))

    if not job or not dataset:
        logger.error(f"Job {job_id} or Dataset {dataset_id} not found")
        return {"error": "Job or dataset not found"}

    # ── Mark job as started ───────────────────────────────────────────────────
    job.status = JobStatus.STARTED.value
    job.started_at = datetime.now(timezone.utc)
    job.celery_task_id = self.request.id
    dataset.status = DatasetStatus.PROCESSING.value
    dataset.processing_started_at = datetime.now(timezone.utc)
    session.commit()

    def progress_callback(pct: int, message: str) -> None:
        """Update job progress in DB and check for cancellation."""
        try:
            # Re-fetch to check for cancellation signal
            fresh_job = session.get(Job, UUID(job_id))
            if fresh_job and fresh_job.status == JobStatus.REVOKED.value:
                raise InterruptedError("Job was cancelled")
            if fresh_job:
                fresh_job.progress_pct = pct
                fresh_job.progress_message = message
                session.commit()
        except InterruptedError:
            raise
        except Exception as e:
            logger.warning(f"Progress update failed: {e}")

    try:
        engine = ProfilingEngine()
        result = engine.profile(
            file_path=file_path,
            file_format=file_format,
            progress_callback=progress_callback,
        )
        result = _to_json_safe(result)
        column_profiles = result["column_profiles"]

        # ── Persist profiling results ─────────────────────────────────────────
        dataset.row_count = result["row_count"]
        dataset.column_count = result["column_count"]
        dataset.memory_usage_bytes = result.get("memory_usage_bytes")
        dataset.schema_info = _schema_from_profiles(column_profiles)
        dataset.profiling_summary = {
            "row_count": result["row_count"],
            "column_count": result["column_count"],
            "duplicate_row_count": result["duplicate_row_count"],
            "duplicate_row_pct": result["duplicate_row_pct"],
            "total_missing_values": result["total_missing_values"],
            "total_missing_pct": result["total_missing_pct"],
        }
        dataset.column_profiles = {"profiles": column_profiles}
        dataset.status = DatasetStatus.READY.value
        dataset.error_message = None
        dataset.processing_completed_at = datetime.now(timezone.utc)

        job.status = JobStatus.SUCCESS.value
        job.progress_pct = 100
        job.progress_message = "Profiling complete"
        job.completed_at = datetime.now(timezone.utc)
        job.error_message = None
        job.error_traceback = None
        job.result = {"row_count": result["row_count"], "column_count": result["column_count"]}
        session.commit()

        logger.info(
            f"Profiling job {job_id} completed successfully",
            dataset_id=dataset_id,
            rows=result["row_count"],
        )
        return result

    except SoftTimeLimitExceeded:
        _fail_job(session, job, dataset, "Job exceeded time limit", "TIMEOUT")
        raise

    except InterruptedError:
        job.status = JobStatus.REVOKED.value
        job.completed_at = datetime.now(timezone.utc)
        dataset.status = DatasetStatus.FAILED.value
        dataset.error_message = "Job was cancelled"
        session.commit()
        return {"cancelled": True}

    except MalformedFileError as exc:
        _fail_job(session, job, dataset, str(exc), type(exc).__name__)
        return {"error": str(exc), "error_type": type(exc).__name__}

    except ProfilingError as exc:
        job.retry_count = self.request.retries + 1
        _fail_job(session, job, dataset, str(exc), type(exc).__name__)
        raise self.retry(exc=exc, countdown=30)

    except Exception as exc:
        tb = traceback.format_exc()
        job.retry_count = self.request.retries + 1
        _fail_job(session, job, dataset, str(exc), "UNEXPECTED_ERROR", tb)
        raise self.retry(exc=exc, countdown=60)


def _fail_job(
    session: Session,
    job: Job,
    dataset: Dataset,
    error_message: str,
    error_type: str,
    traceback_str: str | None = None,
) -> None:
    """Mark job and dataset as failed."""
    try:
        session.rollback()
        job.status = JobStatus.FAILURE.value
        job.completed_at = datetime.now(timezone.utc)
        job.error_message = error_message
        if traceback_str:
            job.error_traceback = traceback_str
        dataset.status = DatasetStatus.FAILED.value
        dataset.error_message = error_message
        session.commit()
        logger.error(
            f"Job {job.id} failed: {error_message}",
            error_type=error_type,
        )
    except Exception as e:
        logger.error(f"Failed to update job failure state: {e}")
        session.rollback()
