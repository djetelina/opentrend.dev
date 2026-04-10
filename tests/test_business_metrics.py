import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from litestar.testing import AsyncTestClient
from opentrend.app import create_app
from opentrend.config import Settings
from opentrend.metrics import (
    PACKAGE_MAPPINGS_SOURCE,
    PACKAGE_MAPPINGS_TOTAL,
    PROJECTS_TOTAL,
    SNAPSHOTS_TOTAL,
    USERS_PROJECT_COUNT,
    USERS_TOTAL,
    _business_metrics_cache,
    refresh_business_metrics,
)


def _mock_session(
    *,
    users: int = 0,
    projects: int = 0,
    mappings: int = 0,
    source_counts: dict[str, int] | None = None,
    snapshot_counts: dict[str, int] | None = None,
    project_owner_counts: list[int] | None = None,
) -> AsyncMock:
    """Build an AsyncMock session that returns the given counts."""
    source_counts = source_counts or {}
    snapshot_counts = snapshot_counts or {}
    project_owner_counts = project_owner_counts or []

    # scalar() is called for: users, projects, mappings, then 5 snapshot tables
    scalar_values = [
        users,
        projects,
        mappings,
        snapshot_counts.get("github", 0),
        snapshot_counts.get("package", 0),
        snapshot_counts.get("traffic", 0),
        snapshot_counts.get("release", 0),
        snapshot_counts.get("referrer", 0),
    ]
    scalar_iter = iter(scalar_values)

    async def _scalar(_stmt):
        return next(scalar_iter)

    # execute() is called for: source GROUP BY, then project-count GROUP BY
    source_rows = MagicMock()
    source_rows.all.return_value = list(source_counts.items())

    owner_rows = MagicMock()
    owner_rows.all.return_value = [
        (uuid.uuid4(), count) for count in project_owner_counts
    ]

    execute_results = iter([source_rows, owner_rows])

    async def _execute(_stmt):
        return next(execute_results)

    session = AsyncMock()
    session.scalar = _scalar
    session.execute = _execute
    return session


@pytest.fixture(autouse=True)
def _clear_cache():
    """Ensure each test starts with an empty TTL cache."""
    _business_metrics_cache.clear()
    yield
    _business_metrics_cache.clear()


@pytest.mark.asyncio
async def test_basic_counts() -> None:
    session = _mock_session(users=10, projects=5, mappings=12)

    await refresh_business_metrics(session)

    assert USERS_TOTAL._value.get() == 10
    assert PROJECTS_TOTAL._value.get() == 5
    assert PACKAGE_MAPPINGS_TOTAL._value.get() == 12


@pytest.mark.asyncio
async def test_package_mappings_by_source() -> None:
    session = _mock_session(
        source_counts={"pypi": 3, "npm": 7, "crates": 2},
    )

    await refresh_business_metrics(session)

    assert PACKAGE_MAPPINGS_SOURCE.labels(source="pypi")._value.get() == 3
    assert PACKAGE_MAPPINGS_SOURCE.labels(source="npm")._value.get() == 7
    assert PACKAGE_MAPPINGS_SOURCE.labels(source="crates")._value.get() == 2


@pytest.mark.asyncio
async def test_snapshot_counts() -> None:
    session = _mock_session(
        snapshot_counts={
            "github": 100,
            "package": 200,
            "traffic": 50,
            "release": 30,
            "referrer": 80,
        },
    )

    await refresh_business_metrics(session)

    assert SNAPSHOTS_TOTAL.labels(kind="github")._value.get() == 100
    assert SNAPSHOTS_TOTAL.labels(kind="package")._value.get() == 200
    assert SNAPSHOTS_TOTAL.labels(kind="traffic")._value.get() == 50
    assert SNAPSHOTS_TOTAL.labels(kind="release")._value.get() == 30
    assert SNAPSHOTS_TOTAL.labels(kind="referrer")._value.get() == 80


@pytest.mark.asyncio
async def test_users_project_count_distribution() -> None:
    """3 users own 1, 3, and 7 projects; 2 users own 0 (total users=5)."""
    session = _mock_session(
        users=5,
        project_owner_counts=[1, 3, 7],
    )

    await refresh_business_metrics(session)

    assert USERS_PROJECT_COUNT.labels(count="0")._value.get() == 2
    assert USERS_PROJECT_COUNT.labels(count="1")._value.get() == 1
    assert USERS_PROJECT_COUNT.labels(count="2")._value.get() == 0
    assert USERS_PROJECT_COUNT.labels(count="3")._value.get() == 1
    assert USERS_PROJECT_COUNT.labels(count="4")._value.get() == 0
    assert USERS_PROJECT_COUNT.labels(count="5+")._value.get() == 1


@pytest.mark.asyncio
async def test_cache_skips_second_call() -> None:
    """Second call within TTL should not re-query the DB."""
    session = _mock_session(users=10, projects=5, mappings=12)
    session2 = _mock_session(users=99, projects=99, mappings=99)

    await refresh_business_metrics(session)
    await refresh_business_metrics(session2)

    # Values should still reflect first call, not second
    assert USERS_TOTAL._value.get() == 10
    assert PROJECTS_TOTAL._value.get() == 5


@pytest.mark.asyncio
async def test_cache_cleared_allows_refresh() -> None:
    """After clearing the cache, the function should re-query."""
    session1 = _mock_session(users=10)
    session2 = _mock_session(users=42)

    await refresh_business_metrics(session1)
    assert USERS_TOTAL._value.get() == 10

    # Expire the cache
    _business_metrics_cache.clear()

    await refresh_business_metrics(session2)
    assert USERS_TOTAL._value.get() == 42


@pytest.mark.asyncio
async def test_db_error_does_not_set_cache() -> None:
    """DB failure should not cache, allowing retry on next scrape."""
    session = AsyncMock()
    session.scalar = AsyncMock(side_effect=RuntimeError("connection lost"))

    await refresh_business_metrics(session)

    # Cache should NOT be set — next call should retry
    assert "done" not in _business_metrics_cache


@pytest.mark.asyncio
async def test_metrics_endpoint_includes_business_metrics(
    settings: Settings,
) -> None:
    """The /metrics endpoint should contain our business gauge names."""
    _business_metrics_cache["done"] = True
    USERS_TOTAL.set(42)

    async with AsyncTestClient(
        app=create_app(settings=settings, run_migrations=False)
    ) as client:
        resp = await client.get("/metrics")

    assert resp.status_code == 200
    body = resp.text
    assert "opentrend_users_total 42.0" in body
