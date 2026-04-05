import pytest

from opentrend.collectors.pypi import PyPICollector


@pytest.fixture()
def pypi_json_response() -> dict:
    return {
        "info": {
            "version": "0.27.0",
        },
        "releases": {
            "0.25.0": [],
            "0.26.0": [],
            "0.27.0": [],
        },
    }


@pytest.fixture()
def pypistats_response() -> dict:
    return {
        "data": {
            "last_day": 50000,
            "last_week": 350000,
            "last_month": 1500000,
        },
        "type": "overall_downloads",
    }


def test_parse_package_info(pypi_json_response: dict) -> None:
    collector = PyPICollector()
    info = collector.parse_package_info(pypi_json_response)
    assert info["latest_version"] == "0.27.0"
    assert info["version_count"] == 3


def test_parse_download_stats(pypistats_response: dict) -> None:
    collector = PyPICollector()
    stats = collector.parse_download_stats(pypistats_response)
    assert stats["downloads_daily"] == 50000
    assert stats["downloads_weekly"] == 350000
    assert stats["downloads_monthly"] == 1500000
