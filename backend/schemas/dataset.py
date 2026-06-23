"""
Dataset-related Pydantic v2 request/response schemas.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class DatasetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)


class DatasetResponse(BaseModel):
    id: UUID
    name: str
    original_filename: str
    file_format: str
    mime_type: str
    file_size_bytes: int
    row_count: int | None
    column_count: int | None
    memory_usage_bytes: int | None
    status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    processing_started_at: datetime | None
    processing_completed_at: datetime | None

    model_config = {"from_attributes": True}


class DatasetListItem(BaseModel):
    id: UUID
    name: str
    original_filename: str
    file_format: str
    file_size_bytes: int
    row_count: int | None
    column_count: int | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ColumnSchema(BaseModel):
    name: str
    dtype: str
    inferred_type: str  # numeric | categorical | datetime | text | boolean
    nullable: bool
    null_count: int
    null_pct: float
    unique_count: int | None
    sample_values: list[Any] = Field(default_factory=list)


class DatasetSchemaResponse(BaseModel):
    dataset_id: UUID
    columns: list[ColumnSchema]
    row_count: int
    column_count: int
    memory_usage_bytes: int
    inferred_at: datetime


class DatasetPreviewResponse(BaseModel):
    dataset_id: UUID
    columns: list[str]
    rows: list[dict[str, Any]]
    total_rows: int
    page: int
    page_size: int
    has_more: bool


class NumericStats(BaseModel):
    mean: float | None
    median: float | None
    std: float | None
    variance: float | None
    min: float | None
    max: float | None
    p25: float | None
    p75: float | None
    p95: float | None
    p99: float | None
    skewness: float | None
    kurtosis: float | None
    outlier_count: int
    outlier_pct: float


class CategoricalStats(BaseModel):
    cardinality: int
    entropy: float | None
    top_values: list[dict[str, Any]]
    rare_category_count: int
    rare_category_pct: float


class DatetimeStats(BaseModel):
    min_date: str | None
    max_date: str | None
    range_days: float | None
    null_count: int
    gap_count: int | None


class TextStats(BaseModel):
    avg_length: float | None
    min_length: int | None
    max_length: int | None
    empty_count: int
    language_hint: str | None


class ColumnProfile(BaseModel):
    column_name: str
    inferred_type: str
    null_count: int
    null_pct: float
    unique_count: int | None = None
    unique_pct: float | None = None
    numeric_stats: NumericStats | None = None
    categorical_stats: CategoricalStats | None = None
    datetime_stats: DatetimeStats | None = None
    text_stats: TextStats | None = None

    @field_validator("unique_pct", "null_pct", mode="before")
    @classmethod
    def coerce_none_to_zero(cls, v: Any) -> float:
        """Coerce None to 0.0 for percentage fields."""
        return 0.0 if v is None else v

    @field_validator("unique_count", mode="before")
    @classmethod
    def coerce_none_to_zero_int(cls, v: Any) -> int:
        """Coerce None to 0 for count fields."""
        return 0 if v is None else v


class DatasetProfilingResponse(BaseModel):
    dataset_id: UUID
    row_count: int
    column_count: int
    memory_usage_bytes: int
    duplicate_row_count: int
    duplicate_row_pct: float
    total_missing_values: int
    total_missing_pct: float
    column_profiles: list[ColumnProfile]
    profiled_at: datetime