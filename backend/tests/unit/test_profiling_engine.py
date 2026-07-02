"""
Unit tests for the streaming profiling engine.
Tests: Welford accumulator, reservoir sampler, type inference, chunk processing.
"""
from __future__ import annotations

import math
import random
import tempfile
import os
import csv

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st

from backend.profiling.engine import (
    ProfilingEngine,
    ReservoirSampler,
    WelfordAccumulator,
    infer_column_type,
)


# ── WelfordAccumulator tests ──────────────────────────────────────────────────
class TestWelfordAccumulator:
    def test_single_value(self):
        acc = WelfordAccumulator()
        acc.update(5.0)
        assert acc.n == 1
        assert acc.mean == 5.0
        assert acc.variance is None  # Need at least 2 values

    def test_two_values(self):
        acc = WelfordAccumulator()
        acc.update(2.0)
        acc.update(4.0)
        assert acc.mean == pytest.approx(3.0)
        assert acc.variance == pytest.approx(2.0)
        assert acc.std == pytest.approx(math.sqrt(2.0))

    def test_matches_numpy(self):
        """Welford mean/variance must match numpy for same data."""
        data = [1.5, 2.3, 4.7, 8.1, 3.2, 9.9, 0.1]
        acc = WelfordAccumulator()
        for v in data:
            acc.update(v)
        assert acc.mean == pytest.approx(np.mean(data), rel=1e-9)
        assert acc.variance == pytest.approx(np.var(data, ddof=1), rel=1e-9)

    def test_ignores_nan(self):
        acc = WelfordAccumulator()
        acc.update(1.0)
        acc.update(float("nan"))
        acc.update(3.0)
        assert acc.n == 2
        assert acc.mean == pytest.approx(2.0)

    def test_ignores_inf(self):
        acc = WelfordAccumulator()
        acc.update(1.0)
        acc.update(float("inf"))
        assert acc.n == 1

    def test_min_max_tracking(self):
        acc = WelfordAccumulator()
        for v in [5.0, 1.0, 9.0, 3.0]:
            acc.update(v)
        assert acc.min_val == 1.0
        assert acc.max_val == 9.0

    @given(
        st.lists(
            st.floats(
                min_value=-1e9,
                max_value=1e9,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=2,
            max_size=100,
        )
    )
    @hyp_settings(max_examples=50)
    def test_property_mean_matches_numpy(self, data):
        acc = WelfordAccumulator()
        for v in data:
            acc.update(v)
        assert acc.mean == pytest.approx(np.mean(data), rel=1e-6, abs=1e-10)


# ── ReservoirSampler tests ────────────────────────────────────────────────────
class TestReservoirSampler:
    def test_fills_reservoir(self):
        sampler = ReservoirSampler(size=10)
        for i in range(5):
            sampler.add(i)
        assert len(sampler.sample) == 5

    def test_bounded_size(self):
        sampler = ReservoirSampler(size=10)
        for i in range(1000):
            sampler.add(i)
        assert len(sampler.sample) == 10

    def test_total_seen(self):
        sampler = ReservoirSampler(size=5)
        for i in range(100):
            sampler.add(i)
        assert sampler.total_seen == 100

    def test_sample_is_subset(self):
        """All sampled values must come from the original stream."""
        data = list(range(1000))
        sampler = ReservoirSampler(size=100)
        for v in data:
            sampler.add(v)
        for v in sampler.sample:
            assert v in data

    def test_uniform_distribution(self):
        """Reservoir sampling should produce approximately uniform distribution."""
        random.seed(42)
        n = 10_000
        k = 1_000
        sampler = ReservoirSampler(size=k)
        for i in range(n):
            sampler.add(i)
        sample = sampler.sample
        # Each element should appear with probability k/n
        # Check that sample covers a reasonable range
        assert min(sample) < n * 0.1
        assert max(sample) > n * 0.9


# ── Type inference tests ──────────────────────────────────────────────────────
class TestTypeInference:
    def test_integer_column(self):
        s = pd.Series([1, 2, 3, 4, 5])
        assert infer_column_type(s) == "numeric"

    def test_float_column(self):
        s = pd.Series([1.1, 2.2, 3.3])
        assert infer_column_type(s) == "numeric"

    def test_bool_column(self):
        s = pd.Series([True, False, True])
        assert infer_column_type(s) == "boolean"

    def test_datetime_column(self):
        s = pd.Series(pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]))
        assert infer_column_type(s) == "datetime"

    def test_categorical_column(self):
        s = pd.Series(["cat", "dog", "bird", "cat", "dog"])
        assert infer_column_type(s) == "categorical"

    def test_text_column(self):
        s = pd.Series(["a" * 200, "b" * 200, "c" * 200])
        assert infer_column_type(s) == "text"


# ── ProfilingEngine integration tests ─────────────────────────────────────────
class TestProfilingEngine:
    def _make_csv(self, rows: list[dict]) -> str:
        """Create a temp CSV file and return its path."""
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        )
        if rows:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        f.close()
        return f.name

    def test_basic_profiling(self):
        rows = [
            {"age": 25, "salary": 50000.0, "city": "NYC"},
            {"age": 30, "salary": 60000.0, "city": "LA"},
            {"age": 35, "salary": 70000.0, "city": "NYC"},
            {"age": 40, "salary": 80000.0, "city": "Chicago"},
        ]
        path = self._make_csv(rows)
        try:
            engine = ProfilingEngine()
            result = engine.profile(path, "csv")
            assert result["row_count"] == 4
            assert result["column_count"] == 3
            assert result["duplicate_row_count"] == 0
            assert len(result["column_profiles"]) == 3
        finally:
            os.unlink(path)

    def test_missing_values_detected(self):
        rows = [
            {"a": 1, "b": "x"},
            {"a": None, "b": "y"},
            {"a": 3, "b": None},
        ]
        path = self._make_csv(rows)
        try:
            engine = ProfilingEngine()
            result = engine.profile(path, "csv")
            assert result["total_missing_values"] > 0
        finally:
            os.unlink(path)

    def test_duplicate_detection(self):
        rows = [
            {"a": 1, "b": "x"},
            {"a": 1, "b": "x"},  # duplicate
            {"a": 2, "b": "y"},
        ]
        path = self._make_csv(rows)
        try:
            engine = ProfilingEngine()
            result = engine.profile(path, "csv")
            assert result["duplicate_row_count"] >= 1
        finally:
            os.unlink(path)

    def test_numeric_stats_computed(self):
        rows = [{"value": i} for i in range(1, 101)]
        path = self._make_csv(rows)
        try:
            engine = ProfilingEngine()
            result = engine.profile(path, "csv")
            numeric_profile = next(
                p for p in result["column_profiles"] if p["column_name"] == "value"
            )
            ns = numeric_profile["numeric_stats"]
            assert ns["mean"] == pytest.approx(50.5, rel=0.01)
            assert ns["min"] == 1.0
            assert ns["max"] == 100.0
        finally:
            os.unlink(path)

    def test_progress_callback_called(self):
        rows = [{"x": i} for i in range(100)]
        path = self._make_csv(rows)
        progress_calls = []
        try:
            engine = ProfilingEngine()
            engine.profile(
                path, "csv",
                progress_callback=lambda pct, msg: progress_calls.append(pct)
            )
            assert len(progress_calls) > 0
            assert progress_calls[-1] == 100
        finally:
            os.unlink(path)

    def test_empty_csv(self):
        path = self._make_csv([])
        try:
            engine = ProfilingEngine()
            result = engine.profile(path, "csv")
            assert result["row_count"] == 0
        finally:
            os.unlink(path)
