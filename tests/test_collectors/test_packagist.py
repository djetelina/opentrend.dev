from opentrend.collectors.packagist import PackagistCollector


def test_parse_package() -> None:
    data = {
        "package": {
            "versions": {
                "3.2.0": {},
                "3.1.0": {},
                "3.0.0": {},
                "dev-master": {},
                "dev-main": {},
            },
            "downloads": {
                "total": 5000000,
                "monthly": 200000,
                "daily": 8000,
            },
            "dependents": 150,
        }
    }
    collector = PackagistCollector()
    info = collector.parse_package(data)
    assert info["latest_version"] == "3.2.0"
    assert info["version_count"] == 3
    assert info["downloads_daily"] == 8000
    assert info["downloads_monthly"] == 200000
    assert info["downloads_total"] == 5000000
    assert info["dependents_count"] == 150


def test_parse_package_all_dev() -> None:
    data = {
        "package": {
            "versions": {"dev-master": {}, "dev-main": {}},
            "downloads": {"total": 100, "monthly": 10, "daily": 1},
            "dependents": 0,
        }
    }
    collector = PackagistCollector()
    info = collector.parse_package(data)
    assert info["latest_version"] is None
    assert info["version_count"] == 0
