"""
Celery application factory with Redis broker/backend.
Configured for production: bounded prefetch, task time limits, retry policies.
"""
from __future__ import annotations

from celery import Celery
from celery.signals import (
    task_failure,
    task_postrun,
    task_prerun,
    task_retry,
    worker_ready,
)
from loguru import logger

from backend.core.config import settings


def create_celery_app() -> Celery:
    app = Celery(settings.APP_NAME)

    app.conf.update(
        # ── Broker / Backend ──────────────────────────────────────────────────
        broker_url=settings.CELERY_BROKER_URL,
        result_backend=settings.CELERY_RESULT_BACKEND,
        # ── Serialization ─────────────────────────────────────────────────────
        task_serializer=settings.CELERY_TASK_SERIALIZER,
        result_serializer=settings.CELERY_RESULT_SERIALIZER,
        accept_content=settings.CELERY_ACCEPT_CONTENT,
        # ── Task behavior ─────────────────────────────────────────────────────
        task_track_started=settings.CELERY_TASK_TRACK_STARTED,
        task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
        task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
        task_acks_late=True,          # Ack only after task completes
        task_reject_on_worker_lost=True,
        task_always_eager=False,
        # ── Worker ────────────────────────────────────────────────────────────
        worker_prefetch_multiplier=settings.CELERY_WORKER_PREFETCH_MULTIPLIER,
        worker_max_tasks_per_child=settings.CELERY_WORKER_MAX_TASKS_PER_CHILD,
        worker_disable_rate_limits=False,
        # ── Result expiry ─────────────────────────────────────────────────────
        result_expires=86_400,        # 24 hours
        result_persistent=True,
        # ── Retry defaults ────────────────────────────────────────────────────
        task_default_retry_delay=60,  # 1 minute
        task_max_retries=3,
        # ── Routing ───────────────────────────────────────────────────────────
        task_routes={
            "backend.workers.tasks.profiling.*": {"queue": "profiling"},
            "backend.workers.tasks.ai.*": {"queue": "ai"},
            "backend.workers.tasks.visualization.*": {"queue": "visualization"},
        },
        task_queues={
            "default": {"exchange": "default", "routing_key": "default"},
            "profiling": {"exchange": "profiling", "routing_key": "profiling"},
            "ai": {"exchange": "ai", "routing_key": "ai"},
            "visualization": {"exchange": "visualization", "routing_key": "visualization"},
        },
        task_default_queue="default",
        # ── Monitoring ────────────────────────────────────────────────────────
        worker_send_task_events=True,
        task_send_sent_event=True,
    )

    # Auto-discover tasks in the workers package
    app.autodiscover_tasks(["backend.workers.tasks"])

    return app


celery_app = create_celery_app()


# ── Celery signal handlers for structured logging ─────────────────────────────
@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    logger.info("Celery worker ready", worker=str(sender))


@task_prerun.connect
def on_task_prerun(task_id, task, args, kwargs, **_):
    logger.info(
        f"Task starting: {task.name}",
        task_id=task_id,
        task_name=task.name,
    )


@task_postrun.connect
def on_task_postrun(task_id, task, args, kwargs, retval, state, **_):
    logger.info(
        f"Task finished: {task.name} state={state}",
        task_id=task_id,
        task_name=task.name,
        state=state,
    )


@task_failure.connect
def on_task_failure(task_id, exception, traceback, sender, **_):
    logger.error(
        f"Task failed: {sender.name}",
        task_id=task_id,
        task_name=sender.name,
        error=str(exception),
    )


@task_retry.connect
def on_task_retry(request, reason, einfo, **_):
    logger.warning(
        f"Task retrying: {request.task}",
        task_id=request.id,
        reason=str(reason),
    )