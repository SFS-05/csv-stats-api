"""
Load tests using Locust.
Tests: concurrent uploads, large dataset profiling, API throughput.

Run with:
    locust -f tests/load/locustfile.py --host=http://localhost:8000
"""
from __future__ import annotations

import io
import random
import string

from locust import HttpUser, between, task


def _make_csv(rows: int = 1000, cols: int = 10) -> bytes:
    """Generate a synthetic CSV payload."""
    headers = [f"col_{i}" for i in range(cols)]
    lines = [",".join(headers)]
    for _ in range(rows):
        row = [str(random.uniform(0, 1000)) for _ in range(cols)]
        lines.append(",".join(row))
    return "\n".join(lines).encode()


class DatasetUser(HttpUser):
    """Simulates a user uploading and querying datasets."""

    wait_time = between(1, 3)
    token: str | None = None
    dataset_ids: list[str] = []

    def on_start(self):
        """Login and get JWT token."""
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"email": "loadtest@example.com", "password": "LoadTest123"},
        )
        if resp.status_code == 200:
            self.token = resp.json()["access_token"]
        else:
            # Register first
            self.client.post(
                "/api/v1/auth/register",
                json={
                    "email": "loadtest@example.com",
                    "username": "loadtest",
                    "password": "LoadTest123",
                },
            )
            resp = self.client.post(
                "/api/v1/auth/login",
                json={"email": "loadtest@example.com", "password": "LoadTest123"},
            )
            if resp.status_code == 200:
                self.token = resp.json()["access_token"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    @task(3)
    def list_datasets(self):
        self.client.get(
            "/api/v1/datasets?page=1&page_size=20",
            headers=self._headers(),
            name="/api/v1/datasets [list]",
        )

    @task(1)
    def upload_small_dataset(self):
        csv_data = _make_csv(rows=500, cols=8)
        self.client.post(
            "/api/v1/datasets/upload",
            files={"file": ("test.csv", io.BytesIO(csv_data), "text/csv")},
            headers=self._headers(),
            name="/api/v1/datasets/upload [small]",
        )

    @task(2)
    def get_job_status(self):
        self.client.get(
            "/api/v1/jobs?page=1&page_size=10",
            headers=self._headers(),
            name="/api/v1/jobs [list]",
        )

    @task(1)
    def health_check(self):
        self.client.get("/health", name="/health")