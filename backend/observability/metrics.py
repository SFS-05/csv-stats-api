"""
Prometheus metrics definitions for the CSV Stats API.
All metrics are registered at module import time and exposed via /metrics.
"""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, Info

# ── HTTP metrics ──────────────────────────────────────────────────────────────
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

HTTP_REQUESTS_IN_FLIGHT = Gauge(
    "http_requests_in_flight",
    "Number of HTTP requests currently being processed",
)

# ── Upload metrics ────────────────────────────────────────────────────────────
UPLOAD_TOTAL = Counter(
    "dataset_uploads_total",
    "Total dataset uploads",
    ["format", "status"],
)

UPLOAD_SIZE_BYTES = Histogram(
    "dataset_upload_size_bytes",
    "Size of uploaded datasets in bytes",
    buckets=[
        1_024, 10_240, 102_400, 1_048_576,
        10_485_760, 104_857_600, 524_288_000,
    ],
)

# ── Profiling metrics ─────────────────────────────────────────────────────────
PROFILING_DURATION_SECONDS = Histogram(
    "profiling_duration_seconds",
    "Time taken to profile a dataset",
    ["format"],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600],
)

PROFILING_ROWS_PROCESSED = Counter(
    "profiling_rows_processed_total",
    "Total rows processed during profiling",
)

PROFILING_ERRORS_TOTAL = Counter(
    "profiling_errors_total",
    "Total profiling failures",
    ["error_type"],
)

# ── Job metrics ───────────────────────────────────────────────────────────────
JOB_QUEUE_SIZE = Gauge(
    "job_queue_size",
    "Number of jobs currently in the queue",
    ["job_type"],
)

JOB_PROCESSING_DURATION_SECONDS = Histogram(
    "job_processing_duration_seconds",
    "Time taken to process a job",
    ["job_type", "status"],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600],
)

JOB_TOTAL = Counter(
    "jobs_total",
    "Total jobs processed",
    ["job_type", "status"],
)

# ── AI metrics ────────────────────────────────────────────────────────────────
AI_REQUESTS_TOTAL = Counter(
    "ai_requests_total",
    "Total AI analysis requests",
    ["model", "status"],
)

AI_REQUEST_DURATION_SECONDS = Histogram(
    "ai_request_duration_seconds",
    "AI request duration in seconds",
    ["model"],
    buckets=[0.5, 1, 2, 5, 10, 20, 30, 60],
)

AI_TOKENS_USED = Counter(
    "ai_tokens_used_total",
    "Total AI tokens consumed",
    ["model", "token_type"],
)

# ── Storage metrics ───────────────────────────────────────────────────────────
STORAGE_OPERATIONS_TOTAL = Counter(
    "storage_operations_total",
    "Total storage operations",
    ["operation", "backend", "status"],
)

STORAGE_OPERATION_DURATION_SECONDS = Histogram(
    "storage_operation_duration_seconds",
    "Storage operation duration",
    ["operation", "backend"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0],
)

# ── Database metrics ──────────────────────────────────────────────────────────
DB_QUERY_DURATION_SECONDS = Histogram(
    "db_query_duration_seconds",
    "Database query duration",
    ["operation"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
)

DB_POOL_SIZE = Gauge("db_pool_size", "Current database connection pool size")
DB_POOL_CHECKED_OUT = Gauge("db_pool_checked_out", "Checked-out database connections")

# ── App info ──────────────────────────────────────────────────────────────────
APP_INFO = Info("csv_stats_api", "CSV Stats API application information")