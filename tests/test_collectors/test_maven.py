from opentrend.collectors.maven import MavenCollector


def test_parse_search() -> None:
    data = {
        "response": {
            "numFound": 1,
            "docs": [
                {
                    "id": "com.google.inject:guice",
                    "g": "com.google.inject",
                    "a": "guice",
                    "latestVersion": "7.0.0",
                    "versionCount": 15,
                }
            ],
        }
    }
    collector = MavenCollector()
    info = collector.parse_search(data)
    assert info is not None
    assert info["latest_version"] == "7.0.0"
    assert info["version_count"] == 15


def test_parse_search_empty() -> None:
    data = {"response": {"numFound": 0, "docs": []}}
    collector = MavenCollector()
    assert collector.parse_search(data) is None
