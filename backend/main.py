"""
FastAPI application factory.
Configures: CORS, security headers, rate limiting, error handlers,
Prometheus metrics, OpenTelemetry tracing, and lifespan events.
"""
from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from prometheus_client import make_asgi_app

from backend.api.v1.router import api_router
from backend.core.config import settings
from backend.core.exceptions import AppError
from backend.core.security import SECURITY_HEADERS
from backend.db.base import engine
from backend.observability.logging import configure_logging
from backend.observability.metrics import (
    APP_INFO,
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_IN_FLIGHT,
    HTTP_REQUESTS_TOTAL,
)


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle."""
    configure_logging()
    logger.info(
        f"Starting {settings.APP_NAME} v{settings.APP_VERSION} "
        f"[{settings.ENVIRONMENT.value}]"
    )

    # Set Prometheus app info
    APP_INFO.info({
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT.value,
    })

    # Ensure storage directory exists
    settings.LOCAL_STORAGE_PATH.mkdir(parents=True, exist_ok=True)

    yield

    # Graceful shutdown
    logger.info("Shutting down application")
    await engine.dispose()


# ── Application factory ───────────────────────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title="CSV Stats API",
        description=(
            "Enterprise-grade dataset profiling and AI-powered analysis platform. "
            "Upload datasets, get statistical profiles, visualizations, and AI insights."
        ),
        version=settings.APP_VERSION,
        docs_url=settings.DOCS_URL if not settings.is_production else None,
        redoc_url=settings.REDOC_URL if not settings.is_production else None,
        openapi_url=settings.OPENAPI_URL if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── Middleware ────────────────────────────────────────────────────────────
    # Trusted host validation
    if settings.is_production:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.ALLOWED_HOSTS,
        )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(o) for o in settings.CORS_ORIGINS],
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "X-Process-Time"],
    )

    # ── Request ID + timing middleware ────────────────────────────────────────
    @app.middleware("http")
    async def request_middleware(request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        start_time = time.perf_counter()

        HTTP_REQUESTS_IN_FLIGHT.inc()
        try:
            response = await call_next(request)
        except Exception as exc:
            logger.exception(f"Unhandled exception: {exc}")
            response = JSONResponse(
                status_code=500,
                content={"error_code": "INTERNAL_ERROR", "message": "Internal server error"},
            )
        finally:
            HTTP_REQUESTS_IN_FLIGHT.dec()

        duration = time.perf_counter() - start_time
        endpoint = request.url.path
        method = request.method

        HTTP_REQUESTS_TOTAL.labels(
            method=method,
            endpoint=endpoint,
            status_code=response.status_code,
        ).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(
            method=method,
            endpoint=endpoint,
        ).observe(duration)

        # Inject security headers
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{duration:.4f}"

        return response

    # ── Exception handlers ────────────────────────────────────────────────────
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        logger.warning(f"AppError: {exc.error_code} — {exc.message}")
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(f"Unhandled exception on {request.url.path}: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error_code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
            },
        )

    # ── Routes ────────────────────────────────────────────────────────────────
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # Prometheus metrics endpoint
    if settings.PROMETHEUS_ENABLED:
        metrics_app = make_asgi_app()
        app.mount("/metrics", metrics_app)

    # Health check
    @app.get("/health", tags=["Health"], include_in_schema=False)
    async def health_check() -> dict:
        return {
            "status": "healthy",
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT.value,
        }

    @app.get("/ready", tags=["Health"], include_in_schema=False)
    async def readiness_check() -> dict:
        """Readiness probe: verify DB and Redis connectivity."""
        checks: dict[str, str] = {}

        # Check DB
        try:
            from sqlalchemy import text
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as exc:
            checks["database"] = f"error: {exc}"

        # Check Redis
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(settings.REDIS_URL)
            await r.ping()
            await r.aclose()
            checks["redis"] = "ok"
        except Exception as exc:
            checks["redis"] = f"error: {exc}"

        all_ok = all(v == "ok" for v in checks.values())
        return JSONResponse(
            status_code=200 if all_ok else 503,
            content={"status": "ready" if all_ok else "degraded", "checks": checks},
        )

    return app


app = create_app()