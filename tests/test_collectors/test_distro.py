from opentrend.collectors.distro import DistroCollector
from opentrend.collectors.registry import get_package_collector, DISTRO_SOURCES


def test_distro_collector_exists() -> None:
    collector = DistroCollector()
    assert collector is not None


def test_distro_sources_all_return_collector() -> None:
    for source in DISTRO_SOURCES:
        c = get_package_collector(source)
        assert isinstance(c, DistroCollector), f"Expected DistroCollector for {source}"
