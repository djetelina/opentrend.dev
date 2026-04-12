import asyncio
import hashlib
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from opentrend.collectors.github import GithubCollector
from opentrend.collectors.registry import get_package_collector
from opentrend.collectors.traffic import TrafficCollector
from opentrend.config import Settings
from opentrend.crypto import try_decrypt_token
from opentrend.metrics import COLLECTION_DURATION, COLLECTION_TOTAL
from opentrend.models.project import PackageMapping, Project
from opentrend.models.snapshot import (
    GithubSnapshot,
    ReleaseDownloadSnapshot,
    TrafficSnapshot,
)
from opentrend.models.user import User
from opentrend.services.dashboard import DashboardService

logger = logging.getLogger(__name__)


def compute_collection_time(project_id: uuid.UUID) -> tuple[int, int]:
    """Return (hour, minute) for a project's daily collection slot."""
    h = int(hashlib.sha256(str(project_id).encode()).hexdigest(), 16)
    return h % 24, (h // 24) % 60


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

    async def _instrumented(name: str, coro, *, final: bool = False) -> bool:
        """Run a collector coroutine with metrics and error handling."""
        start = time.monotonic()
        try:
            await coro
            COLLECTION_TOTAL.labels(collector=name, status="success").inc()
            return True
        except Exception:
            COLLECTION_TOTAL.labels(collector=name, status="error").inc()
            if final:
                logger.exception(
                    "Collection failed for %s (project %s)", name, project_id
                )
            else:
                logger.warning(
                    "Collection failed for %s (project %s), will retry",
                    name,
                    project_id,
                )
            return False
        finally:
            COLLECTION_DURATION.labels(collector=name).observe(time.monotonic() - start)

    async def _collect_github(*, final: bool = False) -> bool:
        if token is None:
            logger.warning(
                "No token for project %s, skipping GitHub collection", project_id
            )
            return True
        async with session_factory() as db:
            return await _instrumented(
                "github",
                GithubCollector(token=token).collect(db, project_id, snapshot_date),
                final=final,
            )

    async def _collect_traffic(*, final: bool = False) -> bool:
        if token is None:
            return True
        async with session_factory() as db:
            return await _instrumented(
                "traffic",
                TrafficCollector(token=token).collect(db, project_id, snapshot_date),
                final=final,
            )

    async def _collect_mapping(mapping, *, final: bool = False) -> bool:
        collector = get_package_collector(mapping.source, github_token=token)
        if collector is None:
            return True
        async with session_factory() as db:
            return await _instrumented(
                mapping.source,
                collector.collect(db, mapping.id, snapshot_date),
                final=final,
            )

    tasks = {
        "github": _collect_github,
        "traffic": _collect_traffic,
        **{
            f"mapping_{m.id}": lambda m=m, **kw: _collect_mapping(m, **kw)
            for m in mappings
        },
    }

    is_final = not retry
    results = await asyncio.gather(*[fn(final=is_final) for fn in tasks.values()])
    failed = [name for name, ok in zip(tasks, results) if not ok]

    if retry and failed:
        retry_delays = [300, 600]  # 5 min, 10 min
        for attempt, delay in enumerate(retry_delays, 1):
            if not failed:
                break
            is_final = attempt == len(retry_delays)
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
            retry_results = await asyncio.gather(
                *[tasks[name](final=is_final) for name in failed]
            )
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


async def cleanup_old_release_snapshots(
    session_factory: async_sessionmaker[AsyncSession],
    retention_days: int = 90,
) -> None:
    """Delete release download snapshots older than retention_days.

    The download_count on GitHub release assets is cumulative, so only the
    latest snapshot per asset matters for current totals.  We keep 90 days
    of history to support the download-trend chart, then discard the rest.
    """
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=retention_days)
    async with session_factory() as session:
        result = await session.execute(
            delete(ReleaseDownloadSnapshot).where(ReleaseDownloadSnapshot.date < cutoff)
        )
        await session.commit()
        if result.rowcount:
            logger.info(
                "Cleaned up %d release download snapshots older than %s",
                result.rowcount,
                cutoff,
            )


def register_project_job(
    scheduler,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    project_id: uuid.UUID,
) -> None:
    """Register a single project for daily collection."""
    hour, minute = compute_collection_time(project_id)
    scheduler.add_job(
        collect_project,
        "cron",
        hour=hour,
        minute=minute,
        args=[session_factory, settings, project_id],
        id=f"collect_project_{project_id}",
        replace_existing=True,
    )
    logger.info(
        "Scheduled project %s collection at %02d:%02d", project_id, hour, minute
    )


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

    # Catch-up: run any projects whose scheduled slot already passed today
    # without a snapshot (e.g. after a deploy that shifts schedule times).
    today = datetime.now(timezone.utc).date()
    now = datetime.now(timezone.utc)
    async with session_factory() as session:
        collected_result = await session.execute(
            select(GithubSnapshot.project_id).where(GithubSnapshot.date == today)
        )
        collected_today = {row[0] for row in collected_result.all()}

    missed = []
    for pid in project_ids:
        if pid in collected_today:
            continue
        hour, minute = compute_collection_time(pid)
        scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if scheduled <= now:
            missed.append(pid)

    if missed:
        logger.info(
            "Catch-up: %d project(s) missed today's slot, queuing now", len(missed)
        )
        for pid in missed:
            scheduler.add_job(
                collect_project,
                args=[session_factory, settings, pid],
                id=f"catchup_{pid}",
                replace_existing=True,
            )

    scheduler.add_job(
        cleanup_old_release_snapshots,
        "cron",
        hour=3,
        minute=17,
        args=[session_factory],
        id="cleanup_old_release_snapshots",
        replace_existing=True,
    )
    logger.info("Scheduled daily release snapshot cleanup at 03:17")
