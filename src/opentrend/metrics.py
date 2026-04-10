"""Prometheus metrics for outgoing HTTP requests and database queries."""

import logging
import time
from urllib.parse import urlparse

import niquests
from cachetools import TTLCache
from niquests.adapters import AsyncHTTPAdapter
from prometheus_client import Counter, Gauge, Histogram
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from urllib3.util.retry import Retry


# --- Outgoing HTTP ---

HTTP_REQUEST_DURATION = Histogram(
    "opentrend_http_out_duration_seconds",
    "Duration of outgoing HTTP requests",
    ["method", "domain", "status"],
    buckets=(0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)

HTTP_REQUEST_TOTAL = Counter(
    "opentrend_http_out_total",
    "Total outgoing HTTP requests",
    ["method", "domain", "status"],
)


async def _on_pre_request(prepared_request, **_kwargs):
    prepared_request._metrics_start = time.monotonic()


async def _on_response(response, **_kwargs):
    start = getattr(response.request, "_metrics_start", None)
    if start is None:
        return
    elapsed = time.monotonic() - start
    domain = urlparse(str(response.request.url)).hostname or "unknown"
    method = response.request.method
    status = str(response.status_code)
    HTTP_REQUEST_DURATION.labels(method=method, domain=domain, status=status).observe(
        elapsed
    )
    HTTP_REQUEST_TOTAL.labels(method=method, domain=domain, status=status).inc()


def instrumented_client(**kwargs) -> niquests.AsyncSession:
    """Create a niquests.AsyncSession with Prometheus instrumentation and connection retries."""
    kwargs.setdefault("timeout", 30)
    session = niquests.AsyncSession(**kwargs)
    retry = Retry(total=3, connect=3, backoff_factor=0.5, backoff_jitter=0.25)
    adapter = AsyncHTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.hooks["pre_request"].append(_on_pre_request)
    session.hooks["response"].append(_on_response)
    return session


# --- Database ---

DB_QUERY_DURATION = Histogram(
    "opentrend_db_query_duration_seconds",
    "Duration of database queries",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5),
)

DB_QUERY_TOTAL = Counter(
    "opentrend_db_query_total",
    "Total database queries executed",
)


# --- Collection jobs ---

COLLECTION_DURATION = Histogram(
    "opentrend_collection_duration_seconds",
    "Duration of a single collector run",
    ["collector"],
    buckets=(1, 5, 10, 30, 60, 120, 300),
)

COLLECTION_TOTAL = Counter(
    "opentrend_collection_total",
    "Total collector runs",
    ["collector", "status"],
)


# --- Business metrics ---

BUSINESS_METRICS_TTL = 300  # seconds

_business_metrics_cache: TTLCache = TTLCache(maxsize=1, ttl=BUSINESS_METRICS_TTL)

USERS_TOTAL = Gauge(
    "opentrend_users_total",
    "Total registered users",
)

PROJECTS_TOTAL = Gauge(
    "opentrend_projects_total",
    "Total projects",
)

PACKAGE_MAPPINGS_TOTAL = Gauge(
    "opentrend_package_mappings_total",
    "Total package mappings",
)

PACKAGE_MAPPINGS_SOURCE = Gauge(
    "opentrend_package_mappings_source",
    "Package mappings per registry",
    ["source"],
)

SNAPSHOTS_TOTAL = Gauge(
    "opentrend_snapshots_total",
    "Total snapshot rows per table",
    ["kind"],
)

USERS_PROJECT_COUNT = Gauge(
    "opentrend_users_project_count",
    "Number of users who own exactly N projects",
    ["count"],
)


logger = logging.getLogger(__name__)


async def refresh_business_metrics(session: AsyncSession) -> None:
    if "done" in _business_metrics_cache:
        return

    try:
        # Deferred to avoid circular import: metrics <- db <- models
        from opentrend.models.user import User
        from opentrend.models.project import Project, PackageMapping
        from opentrend.models.snapshot import (
            GithubSnapshot,
            PackageSnapshot,
            TrafficSnapshot,
            ReleaseDownloadSnapshot,
            TrafficReferrerSnapshot,
        )

        # Simple counts
        users_count = await session.scalar(select(func.count(User.id)))
        projects_count = await session.scalar(select(func.count(Project.id)))
        mappings_count = await session.scalar(select(func.count(PackageMapping.id)))

        USERS_TOTAL.set(users_count or 0)
        PROJECTS_TOTAL.set(projects_count or 0)
        PACKAGE_MAPPINGS_TOTAL.set(mappings_count or 0)

        # Package mappings by source
        source_result = await session.execute(
            select(PackageMapping.source, func.count(PackageMapping.id)).group_by(
                PackageMapping.source
            )
        )
        for source, count in source_result.all():
            PACKAGE_MAPPINGS_SOURCE.labels(source=source).set(count)

        # Snapshot counts
        snapshot_tables = {
            "github": GithubSnapshot,
            "package": PackageSnapshot,
            "traffic": TrafficSnapshot,
            "release": ReleaseDownloadSnapshot,
            "referrer": TrafficReferrerSnapshot,
        }
        for kind, model in snapshot_tables.items():
            count = await session.scalar(select(func.count(model.id)))
            SNAPSHOTS_TOTAL.labels(kind=kind).set(count or 0)

        # User-project distribution
        owner_result = await session.execute(
            select(Project.user_id, func.count(Project.id)).group_by(Project.user_id)
        )
        counts: dict[str, int] = {"0": 0, "1": 0, "2": 0, "3": 0, "4": 0, "5+": 0}
        owners_with_projects = 0
        for _user_id, project_count in owner_result.all():
            owners_with_projects += 1
            if project_count >= 5:
                counts["5+"] += 1
            else:
                counts[str(project_count)] += 1
        counts["0"] = (users_count or 0) - owners_with_projects

        for label, value in counts.items():
            USERS_PROJECT_COUNT.labels(count=label).set(value)

        _business_metrics_cache["done"] = True
    except Exception:
        logger.error("Failed to refresh business metrics", exc_info=True)


def instrument_engine(engine: AsyncEngine) -> None:
    """Attach Prometheus event listeners to a SQLAlchemy async engine."""
    sync_engine = engine.sync_engine

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _before_cursor_execute(conn, *_args):
        conn.info["query_start"] = time.monotonic()

    @event.listens_for(sync_engine, "after_cursor_execute")
    def _after_cursor_execute(conn, *_args):
        start = conn.info.pop("query_start", None)
        if start is not None:
            DB_QUERY_DURATION.observe(time.monotonic() - start)
            DB_QUERY_TOTAL.inc()
