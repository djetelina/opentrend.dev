from opentrend.collectors.npm import NpmCollector


def test_parse_registry_response() -> None:
    data = {
        "dist-tags": {"latest": "5.1.0"},
        "versions": {"5.0.0": {}, "5.1.0": {}, "4.0.0": {}},
    }
    collector = NpmCollector()
    info = collector.parse_registry(data)
    assert info["latest_version"] == "5.1.0"
    assert info["version_count"] == 3
