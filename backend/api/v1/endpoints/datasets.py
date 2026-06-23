"""
Dataset endpoints: upload, list, schema, preview, profiling results, delete.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

import duckdb
from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile, status
from loguru import logger

from backend.api.v1.dependencies import CurrentUser, DBSession
from backend.core.config import settings
from backend.core.exceptions import DatasetNotFoundError
from backend.repositories.dataset_repo import DatasetRepository
from backend.schemas.common import PaginatedResponse
from backend.schemas.dataset import (
    DatasetListItem,
    DatasetPreviewResponse,
    DatasetProfilingResponse,
    DatasetResponse,
    DatasetSchemaResponse,
)
from backend.services.upload_service import UploadService
from backend.storage.s3 import get_storage_backend

router = APIRouter(prefix="/datasets", tags=["Datasets"])


def _schema_from_column_profiles(column_profiles: dict | None) -> dict | None:
    profiles = (column_profiles or {}).get("profiles", [])
    if not profiles:
        return None

    columns = []
    for profile in profiles:
        name = profile.get("column_name")
        if not name:
            continue
        inferred_type = profile.get("inferred_type") or "categorical"
        top_values = (profile.get("categorical_stats") or {}).get("top_values", [])
        sample_values = [
            item.get("value")
            for item in top_values
            if isinstance(item, dict) and "value" in item
        ][:5]
        columns.append(
            {
                "name": name,
                "dtype": inferred_type,
                "inferred_type": inferred_type,
                "nullable": int(profile.get("null_count") or 0) > 0,
                "null_count": int(profile.get("null_count") or 0),
                "null_pct": float(profile.get("null_pct") or 0.0),
                "unique_count": profile.get("unique_count"),
                "sample_values": sample_values,
            }
        )

    return {"columns": columns} if columns else None


@router.post(
    "/upload",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a dataset file for async profiling",
)
async def upload_dataset(
    current_user: CurrentUser,
    session: DBSession,
    file: UploadFile = File(..., description="Dataset file to upload"),
    name: str | None = Form(default=None, description="Optional dataset name"),
) -> dict:
    """
    Upload a dataset file. Supported formats: CSV, TSV, XLSX, XLS, JSON, JSONL, Parquet.
    Returns immediately with a job_id for tracking async processing.
    """
    service = UploadService(session)
    result = await service.upload(
        file=file,
        owner_id=current_user.id,
        dataset_name=name,
    )
    return result


@router.get(
    "",
    response_model=PaginatedResponse[DatasetListItem],
    summary="List datasets owned by the current user",
)
async def list_datasets(
    current_user: CurrentUser,
    session: DBSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
) -> PaginatedResponse[DatasetListItem]:
    repo = DatasetRepository(session)
    offset = (page - 1) * page_size
    datasets, total = await repo.list_by_owner(
        owner_id=current_user.id,
        offset=offset,
        limit=page_size,
        status=status_filter,
    )
    items = [DatasetListItem.model_validate(d) for d in datasets]
    return PaginatedResponse.build(items, total, page, page_size)


@router.get(
    "/{dataset_id}",
    response_model=DatasetResponse,
    summary="Get dataset metadata",
)
async def get_dataset(
    dataset_id: UUID,
    current_user: CurrentUser,
    session: DBSession,
) -> DatasetResponse:
    repo = DatasetRepository(session)
    dataset = await repo.get_by_id_and_owner(dataset_id, current_user.id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return DatasetResponse.model_validate(dataset)


@router.get(
    "/{dataset_id}/schema",
    response_model=DatasetSchemaResponse,
    summary="Get inferred schema for a dataset",
)
async def get_schema(
    dataset_id: UUID,
    current_user: CurrentUser,
    session: DBSession,
) -> DatasetSchemaResponse:
    repo = DatasetRepository(session)
    dataset = await repo.get_by_id_and_owner(dataset_id, current_user.id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    schema_info = dataset.schema_info or _schema_from_column_profiles(dataset.column_profiles)
    if not schema_info:
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail="Schema not yet computed. Check job status.",
        )
    from datetime import datetime
    return DatasetSchemaResponse(
        dataset_id=dataset_id,
        columns=schema_info.get("columns", []),
        row_count=dataset.row_count or 0,
        column_count=dataset.column_count or 0,
        memory_usage_bytes=dataset.memory_usage_bytes or 0,
        inferred_at=dataset.processing_completed_at or datetime.utcnow(),
    )


@router.get(
    "/{dataset_id}/preview",
    response_model=DatasetPreviewResponse,
    summary="Preview dataset rows with server-side pagination",
)
async def preview_dataset(
    dataset_id: UUID,
    current_user: CurrentUser,
    session: DBSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    sort_by: str | None = Query(default=None),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$"),
    filter_col: str | None = Query(default=None),
    filter_val: str | None = Query(default=None),
) -> DatasetPreviewResponse:
    """
    Returns paginated rows using DuckDB for efficient server-side querying.
    Never loads the full dataset into memory.
    """
    repo = DatasetRepository(session)
    dataset = await repo.get_by_id_and_owner(dataset_id, current_user.id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if not dataset.is_ready:
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail="Dataset is not ready yet",
        )

    storage = get_storage_backend()
    file_path = str(settings.LOCAL_STORAGE_PATH / dataset.storage_key)
    if not await storage.exists(dataset.storage_key):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The uploaded source file is missing from local storage. "
                "Schema and profiling can still be shown from saved metadata, "
                "but preview requires deleting this stale dataset and uploading the file again."
            ),
        )

    try:
        rows, columns, total = _query_preview(
            file_path=file_path,
            file_format=dataset.file_format,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            filter_col=filter_col,
            filter_val=filter_val,
        )
    except Exception as exc:
        logger.error(f"Preview query failed: {exc}")
        raise HTTPException(status_code=500, detail="Failed to query dataset")

    return DatasetPreviewResponse(
        dataset_id=dataset_id,
        columns=columns,
        rows=rows,
        total_rows=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


def _query_preview(
    file_path: str,
    file_format: str,
    page: int,
    page_size: int,
    sort_by: str | None,
    sort_order: str,
    filter_col: str | None,
    filter_val: str | None,
) -> tuple[list[dict], list[str], int]:
    """Use DuckDB for efficient in-process SQL querying without loading full dataset."""
    con = duckdb.connect(database=":memory:")

    fmt = file_format.lower()
    if fmt in ("csv", "tsv"):
        sep = "\\t" if fmt == "tsv" else ","
        source = f"read_csv_auto('{file_path}', sep='{sep}')"
    elif fmt == "parquet":
        source = f"read_parquet('{file_path}')"
    elif fmt == "json":
        source = f"read_json_auto('{file_path}')"
    elif fmt == "jsonl":
        source = f"read_ndjson_auto('{file_path}')"
    else:
        # Fallback: try CSV
        source = f"read_csv_auto('{file_path}')"

    # Count total rows
    count_result = con.execute(f"SELECT COUNT(*) FROM {source}").fetchone()
    total = count_result[0] if count_result else 0

    # Build query
    where_clause = ""
    if filter_col and filter_val:
        # Parameterized to prevent injection
        where_clause = f"WHERE CAST(\"{filter_col}\" AS VARCHAR) ILIKE '%{filter_val}%'"

    order_clause = ""
    if sort_by:
        direction = "DESC" if sort_order == "desc" else "ASC"
        order_clause = f'ORDER BY "{sort_by}" {direction}'

    offset = (page - 1) * page_size
    query = f"""
        SELECT * FROM {source}
        {where_clause}
        {order_clause}
        LIMIT {page_size} OFFSET {offset}
    """

    result = con.execute(query)
    columns = [desc[0] for desc in result.description]
    rows = [dict(zip(columns, row)) for row in result.fetchall()]
    con.close()

    return rows, columns, total


@router.get(
    "/{dataset_id}/profiling",
    response_model=DatasetProfilingResponse,
    summary="Get full profiling results for a dataset",
)
async def get_profiling(
    dataset_id: UUID,
    current_user: CurrentUser,
    session: DBSession,
) -> DatasetProfilingResponse:
    repo = DatasetRepository(session)
    dataset = await repo.get_by_id_and_owner(dataset_id, current_user.id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if not dataset.profiling_summary:
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail="Profiling not yet complete",
        )
    from datetime import datetime
    summary = dataset.profiling_summary or {}
    profiles = (dataset.column_profiles or {}).get("profiles", [])

    # Defensive: filter out malformed profiles
    from backend.schemas.dataset import ColumnProfile
    valid_profiles = []
    for idx, profile in enumerate(profiles):
        try:
            valid_profiles.append(ColumnProfile(**profile))
        except Exception as exc:
            logger.warning(
                f"Skipping malformed column profile at index {idx}: {exc}"
            )

    return DatasetProfilingResponse(
        dataset_id=dataset_id,
        row_count=summary.get("row_count", 0),
        column_count=summary.get("column_count", 0),
        memory_usage_bytes=dataset.memory_usage_bytes or 0,
        duplicate_row_count=summary.get("duplicate_row_count", 0),
        duplicate_row_pct=summary.get("duplicate_row_pct", 0.0),
        total_missing_values=summary.get("total_missing_values", 0),
        total_missing_pct=summary.get("total_missing_pct", 0.0),
        column_profiles=valid_profiles,
        profiled_at=dataset.processing_completed_at or datetime.utcnow(),
    )


@router.delete(
    "/{dataset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Soft-delete a dataset",
)
async def delete_dataset(
    dataset_id: UUID,
    current_user: CurrentUser,
    session: DBSession,
):
    repo = DatasetRepository(session)
    dataset = await repo.get_by_id_and_owner(dataset_id, current_user.id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    await repo.soft_delete(dataset_id)
    # Also delete from storage
    try:
        storage = get_storage_backend()
        await storage.delete(dataset.storage_key)
    except Exception as exc:
        logger.warning(f"Storage delete failed for {dataset.storage_key}: {exc}")
