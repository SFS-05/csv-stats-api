"""
Chart data generation service.
Computes chart-ready data structures from profiling results.
All computation is server-side; frontend only renders.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from backend.core.config import settings


def _load_column_sample(
    file_path: str,
    file_format: str,
    column: str,
    max_rows: int = 100_000,
) -> pd.Series:
    """Load a single column sample using chunked reading."""
    fmt = file_format.lower()
    chunks = []
    total = 0

    if fmt in ("csv", "tsv"):
        sep = "\t" if fmt == "tsv" else ","
        for chunk in pd.read_csv(
            file_path, sep=sep, usecols=[column], chunksize=10_000
        ):
            chunks.append(chunk[column])
            total += len(chunk)
            if total >= max_rows:
                break
    elif fmt == "parquet":
        import pyarrow.parquet as pq
        pf = pq.ParquetFile(file_path)
        for batch in pf.iter_batches(batch_size=10_000, columns=[column]):
            chunks.append(batch.to_pandas()[column])
            total += len(batch)
            if total >= max_rows:
                break
    elif fmt in ("xlsx", "xls"):
        df = pd.read_excel(file_path, usecols=[column], nrows=max_rows)
        return df[column]
    else:
        # Fallback: read full file
        if fmt == "json":
            df = pd.read_json(file_path)
        elif fmt == "jsonl":
            df = pd.read_json(file_path, lines=True)
        else:
            df = pd.read_csv(file_path)
        return df[column].head(max_rows)

    if not chunks:
        return pd.Series([], dtype=object)
    return pd.concat(chunks).head(max_rows)


def generate_histogram(
    file_path: str,
    file_format: str,
    column: str,
    bins: int = 30,
) -> dict[str, Any]:
    """Generate histogram data for a numeric column."""
    series = _load_column_sample(file_path, file_format, column)
    numeric = pd.to_numeric(series, errors="coerce").dropna()

    if len(numeric) == 0:
        return {"column": column, "bins": [], "type": "histogram"}

    counts, bin_edges = np.histogram(numeric, bins=bins)
    return {
        "column": column,
        "type": "histogram",
        "bins": [
            {
                "bin_start": round(float(bin_edges[i]), 6),
                "bin_end": round(float(bin_edges[i + 1]), 6),
                "count": int(counts[i]),
                "pct": round(int(counts[i]) / len(numeric) * 100, 4),
            }
            for i in range(len(counts))
        ],
        "total_values": len(numeric),
        "null_count": int(series.isna().sum()),
    }


def generate_bar_chart(
    file_path: str,
    file_format: str,
    column: str,
    top_n: int = 20,
) -> dict[str, Any]:
    """Generate bar chart data for a categorical column."""
    series = _load_column_sample(file_path, file_format, column)
    non_null = series.dropna().astype(str)
    counts = non_null.value_counts().head(top_n)
    total = len(non_null)

    return {
        "column": column,
        "type": "bar",
        "bars": [
            {
                "value": str(val),
                "count": int(cnt),
                "pct": round(int(cnt) / total * 100, 4) if total > 0 else 0,
            }
            for val, cnt in counts.items()
        ],
        "total_values": total,
        "null_count": int(series.isna().sum()),
        "cardinality": int(non_null.nunique()),
    }


def generate_box_plot(
    file_path: str,
    file_format: str,
    column: str,
) -> dict[str, Any]:
    """Generate box plot statistics for a numeric column."""
    series = _load_column_sample(file_path, file_format, column)
    numeric = pd.to_numeric(series, errors="coerce").dropna()

    if len(numeric) == 0:
        return {"column": column, "type": "boxplot", "data": None}

    q1 = float(np.percentile(numeric, 25))
    q3 = float(np.percentile(numeric, 75))
    iqr = q3 - q1
    lower_fence = q1 - 1.5 * iqr
    upper_fence = q3 + 1.5 * iqr

    outliers = numeric[(numeric < lower_fence) | (numeric > upper_fence)]

    return {
        "column": column,
        "type": "boxplot",
        "data": {
            "min": float(numeric.min()),
            "q1": q1,
            "median": float(np.median(numeric)),
            "q3": q3,
            "max": float(numeric.max()),
            "lower_fence": lower_fence,
            "upper_fence": upper_fence,
            "outlier_count": len(outliers),
            "outliers": outliers.head(100).tolist(),
        },
    }


def generate_correlation_matrix(
    file_path: str,
    file_format: str,
    max_columns: int = 20,
) -> dict[str, Any]:
    """Generate Pearson correlation matrix for numeric columns."""
    fmt = file_format.lower()
    if fmt in ("csv", "tsv"):
        sep = "\t" if fmt == "tsv" else ","
        df = pd.read_csv(file_path, sep=sep, nrows=50_000)
    elif fmt == "parquet":
        import pyarrow.parquet as pq
        df = pq.read_table(file_path).to_pandas().head(50_000)
    elif fmt in ("xlsx", "xls"):
        df = pd.read_excel(file_path, nrows=50_000)
    else:
        df = pd.read_csv(file_path, nrows=50_000)

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if len(numeric_cols) > max_columns:
        numeric_cols = numeric_cols[:max_columns]

    if len(numeric_cols) < 2:
        return {"type": "correlation", "columns": [], "matrix": []}

    corr = df[numeric_cols].corr(method="pearson")

    return {
        "type": "correlation",
        "columns": numeric_cols,
        "matrix": [
            [
                round(float(corr.iloc[i, j]), 4) if not math.isnan(corr.iloc[i, j]) else None
                for j in range(len(numeric_cols))
            ]
            for i in range(len(numeric_cols))
        ],
    }


def generate_null_distribution(
    column_profiles: list[dict],
) -> dict[str, Any]:
    """Generate null value distribution chart data from profiling results."""
    bars = sorted(
        [
            {
                "column": p["column_name"],
                "null_count": p["null_count"],
                "null_pct": p["null_pct"],
            }
            for p in column_profiles
            if p.get("null_count", 0) > 0
        ],
        key=lambda x: x["null_pct"],
        reverse=True,
    )
    return {
        "type": "null_distribution",
        "bars": bars,
        "total_columns": len(column_profiles),
        "columns_with_nulls": len(bars),
    }


def generate_time_series(
    file_path: str,
    file_format: str,
    date_column: str,
    value_column: str,
    freq: str = "D",
) -> dict[str, Any]:
    """Generate time-series aggregation for a date + value column pair."""
    fmt = file_format.lower()
    if fmt in ("csv", "tsv"):
        sep = "\t" if fmt == "tsv" else ","
        df = pd.read_csv(
            file_path, sep=sep, usecols=[date_column, value_column], nrows=200_000
        )
    elif fmt in ("xlsx", "xls"):
        df = pd.read_excel(file_path, usecols=[date_column, value_column], nrows=200_000)
    else:
        df = pd.read_csv(file_path, usecols=[date_column, value_column], nrows=200_000)

    df[date_column] = pd.to_datetime(df[date_column], errors="coerce")
    df = df.dropna(subset=[date_column])
    df[value_column] = pd.to_numeric(df[value_column], errors="coerce")
    df = df.set_index(date_column).sort_index()

    agg = df[value_column].resample(freq).mean().dropna()

    return {
        "type": "timeseries",
        "date_column": date_column,
        "value_column": value_column,
        "frequency": freq,
        "points": [
            {"date": str(ts.date()), "value": round(float(val), 6)}
            for ts, val in agg.items()
        ],
    }
