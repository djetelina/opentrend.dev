from opentrend.collectors.crates import CratesCollector


def test_parse_crate_response() -> None:
    data = {
        "crate": {
            "max_version": "1.5.0",
            "downloads": 5000000,
            "recent_downloads": 200000,
        },
        "versions": [{"num": "1.5.0"}, {"num": "1.4.0"}, {"num": "1.3.0"}],
    }
    collector = CratesCollector()
    info = collector.parse_crate(data)
    assert info["latest_version"] == "1.5.0"
    assert info["version_count"] == 3
    assert info["downloads_total"] == 5000000
    assert info["downloads_recent"] == 200000
