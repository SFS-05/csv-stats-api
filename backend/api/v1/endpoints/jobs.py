"""
Job endpoints: status, list, cancel.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from backend.api.v1.dependencies import CurrentUser, DBSession
from backend.repositories.job_repo import JobRepository
from backend.schemas.common import JobStatusResponse, PaginatedResponse
from backend.workers.celery_app import celery_app

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job status and progress",
)
async def get_job_status(
    job_id: UUID,
    current_user: CurrentUser,
    session: DBSession,
) -> JobStatusResponse:
    repo = JobRepository(session)
    job = await repo.get_by_id(job_id)
    if not job or job.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        progress_pct=job.progress_pct,
        progress_message=job.progress_message,
        created_at=job.queued_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration_seconds=job.duration_seconds,
        error_message=job.error_message,
    )


@router.get(
    "",
    response_model=PaginatedResponse[JobStatusResponse],
    summary="List jobs for the current user",
)
async def list_jobs(
    current_user: CurrentUser,
    session: DBSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    job_type: str | None = Query(default=None),
) -> PaginatedResponse[JobStatusResponse]:
    repo = JobRepository(session)
    offset = (page - 1) * page_size
    jobs, total = await repo.list_by_owner(
        owner_id=current_user.id,
        offset=offset,
        limit=page_size,
        status=status_filter,
        job_type=job_type,
    )
    items = [
        JobStatusResponse(
            job_id=j.id,
            status=j.status,
            progress_pct=j.progress_pct,
            progress_message=j.progress_message,
            created_at=j.queued_at,
            started_at=j.started_at,
            completed_at=j.completed_at,
            duration_seconds=j.duration_seconds,
            error_message=j.error_message,
        )
        for j in jobs
    ]
    return PaginatedResponse.build(items, total, page, page_size)


@router.post(
    "/{job_id}/cancel",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Cancel a queued or running job",
)
async def cancel_job(
    job_id: UUID,
    current_user: CurrentUser,
    session: DBSession,
) -> dict:
    repo = JobRepository(session)
    job = await repo.get_by_id(job_id)
    if not job or job.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")

    cancelled = await repo.cancel_job(job_id)
    if not cancelled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job is not in a cancellable state",
        )

    # Revoke the Celery task if it has a task ID
    if job.celery_task_id:
        celery_app.control.revoke(
            job.celery_task_id,
            terminate=True,
            signal="SIGTERM",
        )

    return {"job_id": str(job_id), "status": "revoked"}