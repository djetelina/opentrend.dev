from opentrend.collectors.go import GoCollector


def test_parse_latest() -> None:
    data = {"Version": "v1.6.0", "Time": "2024-01-15T10:00:00Z"}
    collector = GoCollector()
    assert collector.parse_latest(data) == "v1.6.0"


def test_parse_version_list() -> None:
    text = "v1.0.0\nv1.1.0\nv1.2.0\nv1.3.0\nv1.4.0\nv1.5.0\nv1.6.0\n"
    collector = GoCollector()
    assert collector.parse_version_list(text) == 7


def test_parse_version_list_empty() -> None:
    collector = GoCollector()
    assert collector.parse_version_list("") == 0
    assert collector.parse_version_list("\n") == 0
