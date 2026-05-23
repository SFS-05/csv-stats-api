"""
Streaming dataset profiling engine.

Uses chunked processing with Welford's online algorithm for numeric stats,
reservoir sampling for large datasets, and bounded memory strategies.
Supports CSV, TSV, XLSX, JSON, JSONL, and Parquet formats.
"""
from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterator

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from loguru import logger

from backend.core.config import settings
from backend.core.exceptions import MalformedFileError, ProfilingError


# ── Welford online algorithm for streaming numeric stats ──────────────────────
@dataclass
class WelfordAccumulator:
    """
    Computes mean and variance in a single pass using Welford's online algorithm.
    Memory: O(1) regardless of dataset size.
    """
    n: int = 0
    mean: float = 0.0
    M2: float = 0.0
    min_val: float = float("inf")
    max_val: float = float("-inf")

    def update(self, value: float) -> None:
        if math.isnan(value) or math.isinf(value):
            return
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n
        delta2 = value - self.mean
        self.M2 += delta * delta2
        if value < self.min_val:
            self.min_val = value
        if value > self.max_val:
            self.max_val = value

    @property
    def variance(self) -> float | None:
        return self.M2 / (self.n - 1) if self.n > 1 else None

    @property
    def std(self) -> float | None:
        v = self.variance
        return math.sqrt(v) if v is not None else None


# ── Reservoir sampler for bounded memory sampling ─────────────────────────────
class ReservoirSampler:
    """
    Algorithm R reservoir sampling.
    Maintains a fixed-size random sample from a stream.
    Memory: O(k) where k = reservoir size.
    """

    def __init__(self, size: int = 1000) -> None:
        self._size = size
        self._reservoir: list[Any] = []
        self._count = 0

    def add(self, item: Any) -> None:
        self._count += 1
        if len(self._reservoir) < self._size:
            self._reservoir.append(item)
        else:
            j = random.randint(0, self._count - 1)
            if j < self._size:
                self._reservoir[j] = item

    @property
    def sample(self) -> list[Any]:
        return list(self._reservoir)

    @property
    def total_seen(self) -> int:
        return self._count


# ── Column-level profiling state ──────────────────────────────────────────────
@dataclass
class ColumnProfileState:
    name: str
    null_count: int = 0
    total_count: int = 0
    # Numeric
    welford: WelfordAccumulator = field(default_factory=WelfordAccumulator)
    values_for_percentile: ReservoirSampler = field(
        default_factory=lambda: ReservoirSampler(size=settings.PROFILING_SAMPLE_SIZE)
    )
    # Categorical
    value_counter: Counter = field(default_factory=Counter)
    cardinality_exceeded: bool = False
    # Text
    total_length: int = 0
    min_length: int | None = None
    max_length: int | None = None
    empty_count: int = 0
    # Datetime
    min_date: datetime | None = None
    max_date: datetime | None = None


@dataclass
class DatasetProfileState:
    row_count: int = 0
    column_count: int = 0
    duplicate_hashes: set = field(default_factory=set)
    duplicate_count: int = 0
    columns: dict[str, ColumnProfileState] = field(default_factory=dict)


# ── Type inference ────────────────────────────────────────────────────────────
def infer_column_type(series: pd.Series) -> str:
    """Infer semantic column type from a pandas Series."""
    dtype = series.dtype
    if pd.api.types.is_bool_dtype(dtype):
        return "boolean"
    if pd.api.types.is_integer_dtype(dtype) or pd.api.types.is_float_dtype(dtype):
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return "datetime"
    # Try to parse as datetime
    if dtype == object:
        sample = series.dropna().head(100)
        if len(sample) > 0:
            try:
                pd.to_datetime(sample, infer_datetime_format=True)
                return "datetime"
            except Exception:
                pass
        # Check if it looks numeric
        try:
            pd.to_numeric(sample)
            return "numeric"
        except Exception:
            pass
        # Check average string length — long strings are "text"
        avg_len = sample.astype(str).str.len().mean()
        if avg_len > 100:
            return "text"
        return "categorical"
    return "categorical"


# ── Chunk reader ──────────────────────────────────────────────────────────────
def iter_chunks(
    file_path: str,
    file_format: str,
    chunk_size: int = settings.PROFILING_CHUNK_SIZE,
) -> Iterator[pd.DataFrame]:
    """
    Yield DataFrame chunks from a file without loading the entire file.
    Supports CSV, TSV, XLSX, JSON, JSONL, Parquet.
    """
    fmt = file_format.lower()
    try:
        if fmt in ("csv", "tsv"):
            sep = "\t" if fmt == "tsv" else ","
            reader = pd.read_csv(
                file_path,
                sep=sep,
                chunksize=chunk_size,
                low_memory=False,
                on_bad_lines="warn",
            )
            yield from reader

        elif fmt in ("xlsx", "xls"):
            # Excel must be loaded fully — use openpyxl engine
            df = pd.read_excel(file_path, engine="openpyxl" if fmt == "xlsx" else "xlrd")
            for start in range(0, len(df), chunk_size):
                yield df.iloc[start : start + chunk_size]

        elif fmt == "json":
            df = pd.read_json(file_path)
            for start in range(0, len(df), chunk_size):
                yield df.iloc[start : start + chunk_size]

        elif fmt == "jsonl":
            reader = pd.read_json(file_path, lines=True, chunksize=chunk_size)
            yield from reader

        elif fmt == "parquet":
            pf = pq.ParquetFile(file_path)
            for batch in pf.iter_batches(batch_size=chunk_size):
                yield batch.to_pandas()

        else:
            raise MalformedFileError(f"Unsupported format: {fmt!r}")

    except (pd.errors.ParserError, pa.ArrowInvalid, ValueError) as exc:
        raise MalformedFileError(f"Failed to parse {fmt!r} file: {exc}") from exc


# ── Main profiling engine ─────────────────────────────────────────────────────
class ProfilingEngine:
    """
    Streaming profiling engine.
    Processes datasets in chunks to support multi-GB files.
    """

    def __init__(
        self,
        chunk_size: int = settings.PROFILING_CHUNK_SIZE,
        max_cardinality: int = settings.PROFILING_MAX_CARDINALITY,
        outlier_zscore: float = settings.PROFILING_OUTLIER_ZSCORE_THRESHOLD,
    ) -> None:
        self._chunk_size = chunk_size
        self._max_cardinality = max_cardinality
        self._outlier_zscore = outlier_zscore

    def profile(
        self,
        file_path: str,
        file_format: str,
        progress_callback=None,
    ) -> dict:
        """
        Profile a dataset file and return a structured profiling result dict.
        progress_callback(pct: int, message: str) is called periodically.
        """
        state = DatasetProfileState()
        column_types: dict[str, str] = {}
        chunks_processed = 0

        logger.info(f"Starting profiling: {file_path!r} format={file_format}")

        try:
            for chunk in iter_chunks(file_path, file_format, self._chunk_size):
                self._process_chunk(chunk, state, column_types)
                chunks_processed += 1
                if progress_callback:
                    progress_callback(
                        min(90, chunks_processed * 5),
                        f"Processed {state.row_count:,} rows",
                    )
        except MalformedFileError:
            raise
        except Exception as exc:
            raise ProfilingError(f"Profiling failed: {exc}") from exc

        if progress_callback:
            progress_callback(95, "Computing final statistics")

        result = self._finalize(state, column_types)

        if progress_callback:
            progress_callback(100, "Profiling complete")

        logger.info(
            f"Profiling complete: {state.row_count:,} rows, "
            f"{state.column_count} columns"
        )
        return result

    def _process_chunk(
        self,
        chunk: pd.DataFrame,
        state: DatasetProfileState,
        column_types: dict[str, str],
    ) -> None:
        """Update profiling state with a new chunk."""
        state.row_count += len(chunk)
        state.column_count = len(chunk.columns)

        # Duplicate detection via row hash (bounded by reservoir)
        if state.row_count <= 500_000:
            row_hashes = pd.util.hash_pandas_object(chunk, index=False)
            for h in row_hashes:
                if h in state.duplicate_hashes:
                    state.duplicate_count += 1
                else:
                    state.duplicate_hashes.add(h)

        for col in chunk.columns:
            if col not in state.columns:
                state.columns[col] = ColumnProfileState(name=col)
                column_types[col] = infer_column_type(chunk[col])

            col_state = state.columns[col]
            series = chunk[col]
            col_type = column_types[col]

            col_state.total_count += len(series)
            col_state.null_count += series.isna().sum()

            non_null = series.dropna()

            if col_type == "numeric":
                self._update_numeric(col_state, non_null)
            elif col_type == "categorical":
                self._update_categorical(col_state, non_null)
            elif col_type == "datetime":
                self._update_datetime(col_state, non_null)
            elif col_type == "text":
                self._update_text(col_state, non_null)

    def _update_numeric(
        self, state: ColumnProfileState, series: pd.Series
    ) -> None:
        numeric = pd.to_numeric(series, errors="coerce").dropna()
        for val in numeric:
            state.welford.update(float(val))
            state.values_for_percentile.add(float(val))

    def _update_categorical(
        self, state: ColumnProfileState, series: pd.Series
    ) -> None:
        if not state.cardinality_exceeded:
            counts = series.astype(str).value_counts()
            for val, cnt in counts.items():
                state.value_counter[val] += cnt
            if len(state.value_counter) > self._max_cardinality:
                state.cardinality_exceeded = True
                # Keep only top-N to bound memory
                top = state.value_counter.most_common(self._max_cardinality)
                state.value_counter = Counter(dict(top))

    def _update_datetime(
        self, state: ColumnProfileState, series: pd.Series
    ) -> None:
        try:
            dates = pd.to_datetime(series, errors="coerce").dropna()
            if len(dates) == 0:
                return
            chunk_min = dates.min()
            chunk_max = dates.max()
            if state.min_date is None or chunk_min < state.min_date:
                state.min_date = chunk_min.to_pydatetime()
            if state.max_date is None or chunk_max > state.max_date:
                state.max_date = chunk_max.to_pydatetime()
        except Exception:
            pass

    def _update_text(
        self, state: ColumnProfileState, series: pd.Series
    ) -> None:
        lengths = series.astype(str).str.len()
        state.total_length += int(lengths.sum())
        chunk_min = int(lengths.min()) if len(lengths) > 0 else None
        chunk_max = int(lengths.max()) if len(lengths) > 0 else None
        if chunk_min is not None:
            state.min_length = min(state.min_length or chunk_min, chunk_min)
        if chunk_max is not None:
            state.max_length = max(state.max_length or chunk_max, chunk_max)
        state.empty_count += int((series.astype(str).str.strip() == "").sum())

    def _finalize(
        self, state: DatasetProfileState, column_types: dict[str, str]
    ) -> dict:
        """Compute final statistics from accumulated state."""
        column_profiles = []

        for col_name, col_state in state.columns.items():
            col_type = column_types.get(col_name, "categorical")
            null_pct = (
                col_state.null_count / col_state.total_count * 100
                if col_state.total_count > 0
                else 0.0
            )
            non_null_count = col_state.total_count - col_state.null_count

            profile: dict[str, Any] = {
                "column_name": col_name,
                "inferred_type": col_type,
                "null_count": col_state.null_count,
                "null_pct": round(null_pct, 4),
                "unique_count": None,
                "unique_pct": None,
            }

            if col_type == "numeric":
                profile["numeric_stats"] = self._compute_numeric_stats(col_state)
            elif col_type == "categorical":
                profile["categorical_stats"] = self._compute_categorical_stats(
                    col_state, non_null_count
                )
                profile["unique_count"] = len(col_state.value_counter)
                if non_null_count > 0:
                    profile["unique_pct"] = round(
                        len(col_state.value_counter) / non_null_count * 100, 4
                    )
            elif col_type == "datetime":
                profile["datetime_stats"] = self._compute_datetime_stats(col_state)
            elif col_type == "text":
                profile["text_stats"] = self._compute_text_stats(
                    col_state, non_null_count
                )

            column_profiles.append(profile)

        total_cells = state.row_count * state.column_count
        total_missing = sum(c.null_count for c in state.columns.values())

        return {
            "row_count": state.row_count,
            "column_count": state.column_count,
            "memory_usage_bytes": None,  # Computed separately
            "duplicate_row_count": state.duplicate_count,
            "duplicate_row_pct": round(
                state.duplicate_count / state.row_count * 100
                if state.row_count > 0
                else 0.0,
                4,
            ),
            "total_missing_values": total_missing,
            "total_missing_pct": round(
                total_missing / total_cells * 100 if total_cells > 0 else 0.0, 4
            ),
            "column_profiles": column_profiles,
        }

    def _compute_numeric_stats(self, state: ColumnProfileState) -> dict:
        w = state.welford
        sample = sorted(state.values_for_percentile.sample)
        n = len(sample)

        def percentile(p: float) -> float | None:
            if n == 0:
                return None
            idx = int(p / 100 * (n - 1))
            return sample[idx]

        # Skewness and kurtosis from sample
        skewness = kurtosis = None
        if n >= 3 and w.std and w.std > 0:
            arr = np.array(sample)
            mean = np.mean(arr)
            std = np.std(arr, ddof=1)
            if std > 0:
                skewness = float(np.mean(((arr - mean) / std) ** 3))
                kurtosis = float(np.mean(((arr - mean) / std) ** 4) - 3)

        # Outlier detection using IQR
        outlier_count = 0
        if n >= 4:
            q1 = percentile(25) or 0
            q3 = percentile(75) or 0
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            outlier_count = sum(1 for v in sample if v < lower or v > upper)

        return {
            "mean": round(w.mean, 6) if w.n > 0 else None,
            "median": percentile(50),
            "std": round(w.std, 6) if w.std else None,
            "variance": round(w.variance, 6) if w.variance else None,
            "min": w.min_val if w.n > 0 else None,
            "max": w.max_val if w.n > 0 else None,
            "p25": percentile(25),
            "p75": percentile(75),
            "p95": percentile(95),
            "p99": percentile(99),
            "skewness": round(skewness, 6) if skewness is not None else None,
            "kurtosis": round(kurtosis, 6) if kurtosis is not None else None,
            "outlier_count": outlier_count,
            "outlier_pct": round(outlier_count / n * 100, 4) if n > 0 else 0.0,
        }

    def _compute_categorical_stats(
        self, state: ColumnProfileState, non_null_count: int
    ) -> dict:
        counter = state.value_counter
        total = sum(counter.values())

        # Shannon entropy
        entropy = 0.0
        if total > 0:
            for cnt in counter.values():
                p = cnt / total
                if p > 0:
                    entropy -= p * math.log2(p)

        top_values = [
            {"value": val, "count": cnt, "pct": round(cnt / total * 100, 4)}
            for val, cnt in counter.most_common(20)
        ]

        # Rare categories: appear in < 1% of non-null values
        rare_threshold = max(1, non_null_count * 0.01)
        rare_count = sum(1 for cnt in counter.values() if cnt < rare_threshold)

        return {
            "cardinality": len(counter),
            "entropy": round(entropy, 6),
            "top_values": top_values,
            "rare_category_count": rare_count,
            "rare_category_pct": round(
                rare_count / len(counter) * 100 if counter else 0.0, 4
            ),
        }

    def _compute_datetime_stats(self, state: ColumnProfileState) -> dict:
        range_days = None
        if state.min_date and state.max_date:
            range_days = (state.max_date - state.min_date).total_seconds() / 86400

        return {
            "min_date": state.min_date.isoformat() if state.min_date else None,
            "max_date": state.max_date.isoformat() if state.max_date else None,
            "range_days": round(range_days, 2) if range_days is not None else None,
            "null_count": state.null_count,
            "gap_count": None,  # Requires full sort — computed on demand
        }

    def _compute_text_stats(
        self, state: ColumnProfileState, non_null_count: int
    ) -> dict:
        avg_length = (
            state.total_length / non_null_count if non_null_count > 0 else None
        )
        return {
            "avg_length": round(avg_length, 2) if avg_length is not None else None,
            "min_length": state.min_length,
            "max_length": state.max_length,
            "empty_count": state.empty_count,
            "language_hint": None,  # Requires langdetect — computed on demand
        }