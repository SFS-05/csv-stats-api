"""
Job repository — all database access for Job entities.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.job import Job, JobStatus, JobType


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        dataset_id: UUID,
        owner_id: UUID,
        job_type: JobType,
        max_retries: int = 3,
    ) -> Job:
        job = Job(
            dataset_id=dataset_id,
            owner_id=owner_id,
            job_type=job_type.value,
            status=JobStatus.QUEUED.value,
            max_retries=max_retries,
        )
        self._session.add(job)
        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def get_by_id(self, job_id: UUID) -> Job | None:
        result = await self._session.execute(
            select(Job).where(Job.id == job_id)
        )
        return result.scalar_one_or_none()

    async def get_by_celery_task_id(self, celery_task_id: str) -> Job | None:
        result = await self._session.execute(
            select(Job).where(Job.celery_task_id == celery_task_id)
        )
        return result.scalar_one_or_none()

    async def list_by_dataset(
        self, dataset_id: UUID, limit: int = 20
    ) -> Sequence[Job]:
        result = await self._session.execute(
            select(Job)
            .where(Job.dataset_id == dataset_id)
            .order_by(Job.queued_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def list_by_owner(
        self,
        owner_id: UUID,
        offset: int = 0,
        limit: int = 50,
        status: str | None = None,
        job_type: str | None = None,
    ) -> tuple[Sequence[Job], int]:
        from sqlalchemy import func
        query = select(Job).where(Job.owner_id == owner_id)
        if status:
            query = query.where(Job.status == status)
        if job_type:
            query = query.where(Job.job_type == job_type)

        count_result = await self._session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        query = query.order_by(Job.queued_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(query)
        return result.scalars().all(), total

    async def update_status(
        self,
        job_id: UUID,
        status: JobStatus,
        celery_task_id: str | None = None,
        progress_pct: int | None = None,
        progress_message: str | None = None,
        error_message: str | None = None,
        error_traceback: str | None = None,
        result: dict | None = None,
    ) -> None:
        values: dict = {"status": status.value}

        if status == JobStatus.STARTED:
            values["started_at"] = datetime.now(timezone.utc)
        if status in (JobStatus.SUCCESS, JobStatus.FAILURE, JobStatus.REVOKED):
            values["completed_at"] = datetime.now(timezone.utc)
        if celery_task_id is not None:
            values["celery_task_id"] = celery_task_id
        if progress_pct is not None:
            values["progress_pct"] = progress_pct
        if progress_message is not None:
            values["progress_message"] = progress_message
        if error_message is not None:
            values["error_message"] = error_message
        if error_traceback is not None:
            values["error_traceback"] = error_traceback
        if result is not None:
            values["result"] = result

        await self._session.execute(
            update(Job).where(Job.id == job_id).values(**values)
        )

    async def cancel_job(self, job_id: UUID) -> bool:
        """
        Mark a job as revoked. Returns True if the job was in a cancellable state.
        """
        result = await self._session.execute(
            select(Job).where(
                Job.id == job_id,
                Job.status.in_([JobStatus.QUEUED.value, JobStatus.STARTED.value]),
            )
        )
        job = result.scalar_one_or_none()
        if not job:
            return False

        await self._session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(
                status=JobStatus.REVOKED.value,
                completed_at=datetime.now(timezone.utc),
            )
        )
        return True