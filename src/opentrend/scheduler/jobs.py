import asyncio
import hashlib
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from opentrend.collectors.github import GithubCollector
from opentrend.collectors.registry import get_package_collector
from opentrend.collectors.traffic import TrafficCollector
from opentrend.config import Settings
from opentrend.crypto import try_decrypt_token
from opentrend.metrics import COLLECTION_DURATION, COLLECTION_TOTAL
from opentrend.models.project import PackageMapping, Project
from opentrend.models.snapshot import TrafficSnapshot
from opentrend.models.user import User
from opentrend.services.dashboard import DashboardService

logger = logging.getLogger(__name__)


def compute_collection_hour(project_id: uuid.UUID) -> int:
    h = hashlib.sha256(str(project_id).encode()).hexdigest()
    return int(h, 16) % 24


async def collect_project(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    project_id: uuid.UUID,
    *,
    retry: bool = True,
) -> None:
    snapshot_date = datetime.now(timezone.utc).date()

    async with session_factory() as session:
        result = await session.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project is None:
            return

        # Load the project owner's token (optional — needed for GitHub/traffic only)
        user_result = await session.execute(
            select(User).where(User.id == project.user_id)
        )
        user = user_result.scalar_one_or_none()
        encrypted_token = user.github_access_token if user else None

    token = (
        try_decrypt_token(encrypted_token, settings.encryption_key)
        if encrypted_token
        else None
    )

    async with session_factory() as session:
        result = await session.execute(
            select(PackageMapping).where(PackageMapping.project_id == project_id)
        )
        mappings = list(result.scalars().all())

    async def _instrumented(name: str, coro) -> bool:
        """Run a collector coroutine with metrics and error handling."""
        start = time.monotonic()
        try:
            await coro
            COLLECTION_TOTAL.labels(collector=name, status="success").inc()
            return True
        except Exception:
            COLLECTION_TOTAL.labels(collector=name, status="error").inc()
            logger.exception("Collection failed for %s (project %s)", name, project_id)
            return False
        finally:
            COLLECTION_DURATION.labels(collector=name).observe(time.monotonic() - start)

    async def _collect_github() -> bool:
        if token is None:
            logger.warning(
                "No token for project %s, skipping GitHub collection", project_id
            )
            return True
        return await _instrumented("github", _run_github())

    async def _run_github():
        async with session_factory() as db:
            await GithubCollector(token=token).collect(db, project_id, snapshot_date)

    async def _collect_traffic() -> bool:
        if token is None:
            return True
        return await _instrumented("traffic", _run_traffic())

    async def _run_traffic():
        async with session_factory() as db:
            await TrafficCollector(token=token).collect(db, project_id, snapshot_date)

    async def _collect_mapping(mapping) -> bool:
        collector = get_package_collector(mapping.source, github_token=token)
        if collector is None:
            return True
        return await _instrumented(mapping.source, _run_mapping(collector, mapping))

    async def _run_mapping(collector, mapping):
        async with session_factory() as db:
            await collector.collect(db, mapping.id, snapshot_date)

    tasks = {
        "github": _collect_github,
        "traffic": _collect_traffic,
        **{f"mapping_{m.id}": lambda m=m: _collect_mapping(m) for m in mappings},
    }

    results = await asyncio.gather(*[fn() for fn in tasks.values()])
    failed = [name for name, ok in zip(tasks, results) if not ok]

    if retry and failed:
        retry_delays = [300, 600]  # 5 min, 10 min
        for attempt, delay in enumerate(retry_delays, 1):
            if not failed:
                break
            logger.info(
                "Retrying %d failed collector(s) for project %s in %ds (attempt %d/%d): %s",
                len(failed),
                project_id,
                delay,
                attempt,
                len(retry_delays),
                ", ".join(failed),
            )
            await asyncio.sleep(delay)
            retry_results = await asyncio.gather(*[tasks[name]() for name in failed])
            failed = [name for name, ok in zip(failed, retry_results) if not ok]

    if failed:
        logger.warning(
            "Collectors still failing for project %s: %s",
            project_id,
            ", ".join(failed),
        )

    # Compute reach score after all collectors have run
    await recalc_reach(session_factory, project_id)


async def recalc_reach(
    session_factory: async_sessionmaker[AsyncSession],
    project_id: uuid.UUID,
) -> None:
    """Recompute and store the reach score for a single project."""
    try:
        async with session_factory() as session:
            dashboard = DashboardService(session)
            latest_gh = await dashboard.get_latest_github_snapshot(project_id)
            if latest_gh:
                latest_pkg = await dashboard.get_latest_package_snapshots(project_id)
                result = await session.execute(
                    select(Project).where(Project.id == project_id)
                )
                proj = result.scalar_one()
                matrix = DashboardService.format_packaging_matrix(
                    proj.package_mappings,
                    latest_pkg,
                    latest_gh.latest_release_tag,
                )
                total_downloads = DashboardService.compute_total_downloads(matrix)

                since_30d = datetime.now(timezone.utc).date() - timedelta(days=30)
                traffic_result = await session.execute(
                    select(
                        func.coalesce(func.sum(TrafficSnapshot.views), 0),
                        func.coalesce(func.sum(TrafficSnapshot.clones), 0),
                    ).where(
                        TrafficSnapshot.project_id == project_id,
                        TrafficSnapshot.date >= since_30d,
                    )
                )
                tv, tc = traffic_result.one()

                latest_gh.reach_score = DashboardService.compute_reach(
                    latest_gh,
                    matrix,
                    total_downloads,
                    tv,
                    tc,
                )
                await session.commit()
                logger.info(
                    "Reach score updated for project %s: %d",
                    project_id,
                    latest_gh.reach_score,
                )
    except Exception:
        logger.exception("Reach score computation failed for project %s", project_id)


async def recalc_all_reach(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Recompute reach scores for all projects (bounded concurrency)."""
    async with session_factory() as session:
        result = await session.execute(select(Project.id))
        project_ids = [row[0] for row in result.all()]

    sem = asyncio.Semaphore(5)

    async def _bounded(pid: uuid.UUID) -> None:
        async with sem:
            await recalc_reach(session_factory, pid)

    await asyncio.gather(*[_bounded(pid) for pid in project_ids])


def register_project_job(
    scheduler,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    project_id: uuid.UUID,
) -> None:
    """Register a single project for daily collection."""
    hour = compute_collection_hour(project_id)
    scheduler.add_job(
        collect_project,
        "cron",
        hour=hour,
        minute=0,
        args=[session_factory, settings, project_id],
        id=f"collect_project_{project_id}",
        replace_existing=True,
    )
    logger.info("Scheduled project %s collection at %02d:00", project_id, hour)


async def schedule_daily_collections(
    scheduler,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    """Register APScheduler jobs for all projects, staggered by hash."""
    async with session_factory() as session:
        result = await session.execute(select(Project.id))
        project_ids = [row[0] for row in result.all()]

    for pid in project_ids:
        register_project_job(scheduler, session_factory, settings, pid)
