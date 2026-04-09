"""Prometheus metrics for outgoing HTTP requests and database queries."""

import time
from urllib.parse import urlparse

import niquests
from niquests.adapters import AsyncHTTPAdapter
from prometheus_client import Counter, Histogram
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine
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
