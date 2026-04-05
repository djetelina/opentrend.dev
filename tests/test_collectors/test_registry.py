from opentrend.collectors.registry import get_package_collector
from opentrend.collectors.pypi import PyPICollector
from opentrend.collectors.npm import NpmCollector
from opentrend.collectors.aur import AURCollector
from opentrend.collectors.chocolatey import ChocolateyCollector
from opentrend.collectors.distro import DistroCollector


def test_get_pypi_collector() -> None:
    c = get_package_collector("pypi")
    assert isinstance(c, PyPICollector)


def test_get_npm_collector() -> None:
    c = get_package_collector("npm")
    assert isinstance(c, NpmCollector)


def test_get_aur_collector() -> None:
    c = get_package_collector("aur")
    assert isinstance(c, AURCollector)


def test_get_chocolatey_collector() -> None:
    c = get_package_collector("chocolatey")
    assert isinstance(c, ChocolateyCollector)


def test_get_distro_collector() -> None:
    for source in ["debian", "arch", "alpine", "homebrew", "nix", "fedora"]:
        c = get_package_collector(source)
        assert isinstance(c, DistroCollector), f"Expected DistroCollector for {source}"


def test_get_unknown_collector_returns_none() -> None:
    assert get_package_collector("unknown") is None
