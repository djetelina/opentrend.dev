from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date

import json as json_mod

import niquests
import pytest

from opentrend.collectors.traffic import TrafficCollector


def _mock_response(status_code: int, json_data: dict) -> niquests.Response:
    resp = niquests.Response()
    resp.status_code = status_code
    resp._content = json_mod.dumps(json_data).encode()
    resp.headers["Content-Type"] = "application/json"
    return resp


@pytest.mark.asyncio
async def test_collect_upserts_traffic_data() -> None:
    """TrafficCollector should parse clones, views, and referrers into snapshots."""
    clones_json = {
        "count": 10,
        "uniques": 5,
        "clones": [
            {"timestamp": "2026-04-01T00:00:00Z", "count": 6, "uniques": 3},
            {"timestamp": "2026-04-02T00:00:00Z", "count": 4, "uniques": 2},
        ],
    }
    views_json = {
        "count": 100,
        "uniques": 50,
        "views": [
            {"timestamp": "2026-04-01T00:00:00Z", "count": 60, "uniques": 30},
            {"timestamp": "2026-04-02T00:00:00Z", "count": 40, "uniques": 20},
        ],
    }
    referrers_json = [
        {"referrer": "Google", "count": 50, "uniques": 25},
    ]

    # Mock the project lookup
    mock_project = MagicMock()
    mock_project.github_repo = "owner/repo"

    mock_session = AsyncMock()
    # First execute: project lookup, then traffic snapshot lookups, then referrer lookups
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = mock_project
    mock_result.scalar_one_or_none.return_value = None  # no existing snapshots

    mock_session.execute.return_value = mock_result

    responses = [
        _mock_response(200, clones_json),
        _mock_response(200, views_json),
        _mock_response(200, referrers_json),
    ]
    call_count = 0

    async def mock_get(*args, **kwargs):
        nonlocal call_count
        resp = responses[call_count]
        call_count += 1
        return resp

    mock_client = AsyncMock()
    mock_client.get = mock_get
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "opentrend.collectors.traffic.instrumented_client", return_value=mock_client
    ):
        collector = TrafficCollector(token="test-token")
        await collector.collect(
            mock_session, project_id=1, snapshot_date=date(2026, 4, 2)
        )

    # Should have added snapshots via session.add
    assert mock_session.add.call_count >= 2  # at least 2 daily + 1 referrer
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_collect_skips_on_403() -> None:
    """TrafficCollector should skip gracefully if traffic API returns 403."""
    mock_project = MagicMock()
    mock_project.github_repo = "owner/repo"

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = mock_project
    mock_session.execute.return_value = mock_result

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_response(403, {}))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "opentrend.collectors.traffic.instrumented_client", return_value=mock_client
    ):
        collector = TrafficCollector(token="test-token")
        await collector.collect(
            mock_session, project_id=1, snapshot_date=date(2026, 4, 2)
        )

    # Should not commit since we returned early
    mock_session.commit.assert_not_awaited()
