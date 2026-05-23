"""
Visualization endpoints: histogram, bar chart, box plot, correlation, null distribution.
All chart data is computed server-side and returned as JSON for frontend rendering.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from loguru import logger

from backend.api.v1.dependencies import CurrentUser, DBSession
from backend.core.config import settings
from backend.repositories.dataset_repo import DatasetRepository
from backend.visualization.charts import (
    generate_bar_chart,
    generate_box_plot,
    generate_correlation_matrix,
    generate_histogram,
    generate_null_distribution,
    generate_time_series,
)

router = APIRouter(prefix="/datasets/{dataset_id}/charts", tags=["Visualizations"])


async def _get_ready_dataset(dataset_id: UUID, current_user, session):
    """Shared helper: fetch dataset and verify it's ready."""
    repo = DatasetRepository(session)
    dataset = await repo.get_by_id_and_owner(dataset_id, current_user.id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if not dataset.is_ready:
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail="Dataset profiling is not complete yet",
        )
    return dataset


@router.get("/histogram", summary="Get histogram data for a numeric column")
async def get_histogram(
    dataset_id: UUID,
    current_user: CurrentUser,
    session: DBSession,
    column: str = Query(..., description="Column name"),
    bins: int = Query(default=30, ge=5, le=100),
) -> dict:
    dataset = await _get_ready_dataset(dataset_id, current_user, session)
    file_path = str(settings.LOCAL_STORAGE_PATH / dataset.storage_key)
    try:
        return generate_histogram(file_path, dataset.file_format, column, bins)
    except Exception as exc:
        logger.error(f"Histogram generation failed: {exc}")
        raise HTTPException(status_code=500, detail="Chart generation failed")


@router.get("/bar", summary="Get bar chart data for a categorical column")
async def get_bar_chart(
    dataset_id: UUID,
    current_user: CurrentUser,
    session: DBSession,
    column: str = Query(..., description="Column name"),
    top_n: int = Query(default=20, ge=5, le=100),
) -> dict:
    dataset = await _get_ready_dataset(dataset_id, current_user, session)
    file_path = str(settings.LOCAL_STORAGE_PATH / dataset.storage_key)
    try:
        return generate_bar_chart(file_path, dataset.file_format, column, top_n)
    except Exception as exc:
        logger.error(f"Bar chart generation failed: {exc}")
        raise HTTPException(status_code=500, detail="Chart generation failed")


@router.get("/boxplot", summary="Get box plot statistics for a numeric column")
async def get_box_plot(
    dataset_id: UUID,
    current_user: CurrentUser,
    session: DBSession,
    column: str = Query(..., description="Column name"),
) -> dict:
    dataset = await _get_ready_dataset(dataset_id, current_user, session)
    file_path = str(settings.LOCAL_STORAGE_PATH / dataset.storage_key)
    try:
        return generate_box_plot(file_path, dataset.file_format, column)
    except Exception as exc:
        logger.error(f"Box plot generation failed: {exc}")
        raise HTTPException(status_code=500, detail="Chart generation failed")


@router.get("/correlation", summary="Get Pearson correlation matrix for numeric columns")
async def get_correlation(
    dataset_id: UUID,
    current_user: CurrentUser,
    session: DBSession,
    max_columns: int = Query(default=20, ge=2, le=50),
) -> dict:
    dataset = await _get_ready_dataset(dataset_id, current_user, session)
    file_path = str(settings.LOCAL_STORAGE_PATH / dataset.storage_key)
    try:
        return generate_correlation_matrix(file_path, dataset.file_format, max_columns)
    except Exception as exc:
        logger.error(f"Correlation matrix generation failed: {exc}")
        raise HTTPException(status_code=500, detail="Chart generation failed")


@router.get("/nulls", summary="Get null value distribution across all columns")
async def get_null_distribution(
    dataset_id: UUID,
    current_user: CurrentUser,
    session: DBSession,
) -> dict:
    dataset = await _get_ready_dataset(dataset_id, current_user, session)
    if not dataset.column_profiles:
        raise HTTPException(status_code=425, detail="Profiling not complete")
    profiles = (dataset.column_profiles or {}).get("profiles", [])
    return generate_null_distribution(profiles)


@router.get("/timeseries", summary="Get time-series aggregation for date + value columns")
async def get_time_series(
    dataset_id: UUID,
    current_user: CurrentUser,
    session: DBSession,
    date_column: str = Query(..., description="Date/datetime column name"),
    value_column: str = Query(..., description="Numeric value column name"),
    freq: str = Query(default="D", description="Resample frequency: D, W, M, Y"),
) -> dict:
    if freq not in ("D", "W", "M", "Y", "H"):
        raise HTTPException(status_code=400, detail="Invalid frequency. Use D, W, M, Y, or H")
    dataset = await _get_ready_dataset(dataset_id, current_user, session)
    file_path = str(settings.LOCAL_STORAGE_PATH / dataset.storage_key)
    try:
        return generate_time_series(
            file_path, dataset.file_format, date_column, value_column, freq
        )
    except Exception as exc:
        logger.error(f"Time series generation failed: {exc}")
        raise HTTPException(status_code=500, detail="Chart generation failed")