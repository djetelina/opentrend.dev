import uuid
from abc import ABC, abstractmethod
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from typing import Unpack

from opentrend.models.project import PackageMapping
from opentrend.models.snapshot import PackageSnapshot
from opentrend.types import PackageSnapshotData


class ProjectCollector(ABC):
    """Collector that operates on a project (GitHub, Traffic)."""

    @abstractmethod
    async def collect(
        self, session: AsyncSession, project_id: uuid.UUID, snapshot_date: date
    ) -> None: ...


class PackageCollector(ABC):
    """Collector that operates on a package mapping (PyPI, npm, crates, etc.)."""

    @abstractmethod
    async def collect(
        self, session: AsyncSession, mapping_id: int, snapshot_date: date
    ) -> None: ...

    @staticmethod
    async def get_mapping(session: AsyncSession, mapping_id: int) -> PackageMapping:
        result = await session.execute(
            select(PackageMapping).where(PackageMapping.id == mapping_id)
        )
        return result.scalar_one()

    @staticmethod
    async def upsert_package_snapshot(
        session: AsyncSession,
        mapping_id: int,
        snapshot_date: date,
        **kwargs: Unpack[PackageSnapshotData],
    ) -> PackageSnapshot:
        """Insert or update a package snapshot for the given mapping and date."""
        result = await session.execute(
            select(PackageSnapshot).where(
                PackageSnapshot.package_mapping_id == mapping_id,
                PackageSnapshot.date == snapshot_date,
            )
        )
        snapshot = result.scalar_one_or_none()
        if snapshot:
            for key, value in kwargs.items():
                if value is not None:
                    setattr(snapshot, key, value)
        else:
            snapshot = PackageSnapshot(
                package_mapping_id=mapping_id,
                date=snapshot_date,
                **kwargs,
            )
            session.add(snapshot)
        return snapshot
