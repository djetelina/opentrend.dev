from opentrend.collectors.nuget import NuGetCollector


def test_parse_search_exact_match() -> None:
    data = {
        "data": [
            {
                "id": "Newtonsoft.Json",
                "version": "13.0.3",
                "totalDownloads": 3000000000,
                "versions": [
                    {"version": "13.0.3", "downloads": 500000},
                    {"version": "13.0.2", "downloads": 400000},
                    {"version": "12.0.3", "downloads": 300000},
                ],
            }
        ]
    }
    collector = NuGetCollector()
    info = collector.parse_search(data, "Newtonsoft.Json")
    assert info is not None
    assert info["latest_version"] == "13.0.3"
    assert info["version_count"] == 3
    assert info["downloads_total"] == 3000000000


def test_parse_search_case_insensitive() -> None:
    data = {
        "data": [
            {"id": "Serilog", "version": "4.0.0", "totalDownloads": 100, "versions": []}
        ]
    }
    collector = NuGetCollector()
    info = collector.parse_search(data, "serilog")
    assert info is not None
    assert info["latest_version"] == "4.0.0"


def test_parse_search_no_match() -> None:
    data = {
        "data": [
            {
                "id": "SomeOtherPackage",
                "version": "1.0.0",
                "totalDownloads": 0,
                "versions": [],
            }
        ]
    }
    collector = NuGetCollector()
    info = collector.parse_search(data, "MyPackage")
    assert info is None
