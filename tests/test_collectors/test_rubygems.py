from opentrend.collectors.rubygems import RubyGemsCollector


def test_parse_gem_response() -> None:
    data = {
        "version": "7.1.0",
        "downloads": 400000000,
        "version_downloads": 5000000,
    }
    collector = RubyGemsCollector()
    info = collector.parse_gem(data)
    assert info["latest_version"] == "7.1.0"
    assert info["downloads_total"] == 400000000
    assert info["downloads_version"] == 5000000


def test_parse_versions_response() -> None:
    versions = [{"number": "7.1.0"}, {"number": "7.0.0"}, {"number": "6.1.0"}]
    assert len(versions) == 3
