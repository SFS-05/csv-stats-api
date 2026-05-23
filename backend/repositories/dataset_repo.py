"""
Dataset repository — all database access for Dataset entities.
Isolates SQL from business logic. Uses async SQLAlchemy 2.0 style.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.dataset import Dataset, DatasetStatus


class DatasetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        owner_id: UUID,
        name: str,
        original_filename: str,
        storage_key: str,
        file_format: str,
        mime_type: str,
        file_size_bytes: int,
        checksum_sha256: str | None = None,
    ) -> Dataset:
        dataset = Dataset(
            owner_id=owner_id,
            name=name,
            original_filename=original_filename,
            storage_key=storage_key,
            file_format=file_format,
            mime_type=mime_type,
            file_size_bytes=file_size_bytes,
            checksum_sha256=checksum_sha256,
            status=DatasetStatus.UPLOADED.value,
        )
        self._session.add(dataset)
        await self._session.flush()
        await self._session.refresh(dataset)
        return dataset

    async def get_by_id(self, dataset_id: UUID) -> Dataset | None:
        result = await self._session.execute(
            select(Dataset).where(
                Dataset.id == dataset_id,
                Dataset.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_and_owner(
        self, dataset_id: UUID, owner_id: UUID
    ) -> Dataset | None:
        result = await self._session.execute(
            select(Dataset).where(
                Dataset.id == dataset_id,
                Dataset.owner_id == owner_id,
                Dataset.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_by_owner(
        self,
        owner_id: UUID,
        offset: int = 0,
        limit: int = 50,
        status: str | None = None,
    ) -> tuple[Sequence[Dataset], int]:
        query = select(Dataset).where(
            Dataset.owner_id == owner_id,
            Dataset.deleted_at.is_(None),
        )
        if status:
            query = query.where(Dataset.status == status)

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self._session.execute(count_query)
        total = total_result.scalar_one()

        query = query.order_by(Dataset.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(query)
        return result.scalars().all(), total

    async def update_status(
        self,
        dataset_id: UUID,
        status: DatasetStatus,
        error_message: str | None = None,
    ) -> None:
        values: dict = {
            "status": status.value,
            "updated_at": datetime.now(timezone.utc),
        }
        if error_message is not None:
            values["error_message"] = error_message
        await self._session.execute(
            update(Dataset).where(Dataset.id == dataset_id).values(**values)
        )

    async def update_profiling_results(
        self,
        dataset_id: UUID,
        row_count: int,
        column_count: int,
        memory_usage_bytes: int | None,
        schema_info: dict,
        profiling_summary: dict,
        column_profiles: dict,
    ) -> None:
        await self._session.execute(
            update(Dataset)
            .where(Dataset.id == dataset_id)
            .values(
                row_count=row_count,
                column_count=column_count,
                memory_usage_bytes=memory_usage_bytes,
                schema_info=schema_info,
                profiling_summary=profiling_summary,
                column_profiles=column_profiles,
                status=DatasetStatus.READY.value,
                processing_completed_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )

    async def soft_delete(self, dataset_id: UUID) -> None:
        await self._session.execute(
            update(Dataset)
            .where(Dataset.id == dataset_id)
            .values(
                deleted_at=datetime.now(timezone.utc),
                status=DatasetStatus.DELETED.value,
                updated_at=datetime.now(timezone.utc),
            )
        )

    async def save_ai_summary(self, dataset_id: UUID, ai_summary: dict) -> None:
        await self._session.execute(
            update(Dataset)
            .where(Dataset.id == dataset_id)
            .values(
                ai_summary=ai_summary,
                updated_at=datetime.now(timezone.utc),
            )
        )