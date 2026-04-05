"""Backfill reach_score for all existing github_snapshots.

NOTE: Uses DashboardService.compute_reach for the formula — keep in sync.
"""

import asyncio
import os
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from opentrend.models.project import PackageMapping
from opentrend.models.snapshot import GithubSnapshot, PackageSnapshot, TrafficSnapshot
from opentrend.services.dashboard import DashboardService


async def backfill() -> None:
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://opentrend:opentrend@localhost:5432/opentrend",
    )
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        result = await session.execute(
            select(GithubSnapshot).order_by(
                GithubSnapshot.project_id, GithubSnapshot.date
            )
        )
        snapshots = list(result.scalars().all())
        print(f"Processing {len(snapshots)} snapshots...")

        for i, gh in enumerate(snapshots):
            try:
                pm_result = await session.execute(
                    select(PackageMapping.id).where(
                        PackageMapping.project_id == gh.project_id
                    )
                )
                mapping_ids = [r[0] for r in pm_result.all()]

                source_count = 0
                total_downloads = 0
                total_dependents = 0
                for mid in mapping_ids:
                    pkg_result = await session.execute(
                        select(PackageSnapshot)
                        .where(
                            PackageSnapshot.package_mapping_id == mid,
                            PackageSnapshot.date <= gh.date,
                        )
                        .order_by(PackageSnapshot.date.desc())
                        .limit(1)
                    )
                    pkg = pkg_result.scalar_one_or_none()
                    if pkg and pkg.latest_version:
                        source_count += 1
                    if pkg:
                        if pkg.downloads_monthly:
                            total_downloads += pkg.downloads_monthly
                        elif pkg.downloads_daily:
                            total_downloads += pkg.downloads_daily * 30
                        total_dependents += pkg.dependents_count or 0

                date_boundary = gh.date - timedelta(days=30)
                traffic_result = await session.execute(
                    select(
                        func.coalesce(func.sum(TrafficSnapshot.views), 0),
                        func.coalesce(func.sum(TrafficSnapshot.clones), 0),
                    ).where(
                        TrafficSnapshot.project_id == gh.project_id,
                        TrafficSnapshot.date <= gh.date,
                        TrafficSnapshot.date > date_boundary,
                    )
                )
                tv, tc = traffic_result.one()

                # Build a minimal matrix for compute_reach
                matrix = [
                    {"version": "x", "dependents_count": total_dependents}
                ] * source_count
                reach = DashboardService.compute_reach(
                    gh, matrix, total_downloads, tv, tc
                )

                await session.execute(
                    update(GithubSnapshot)
                    .where(GithubSnapshot.id == gh.id)
                    .values(reach_score=reach)
                )
            except Exception as exc:
                print(f"  Failed snapshot {gh.id}: {exc}")
                continue

            if (i + 1) % 50 == 0:
                print(f"  {i + 1}/{len(snapshots)}...")
                await session.commit()

        await session.commit()
        print(f"Done. Backfilled {len(snapshots)} snapshots.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(backfill())
