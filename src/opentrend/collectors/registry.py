from opentrend.collectors.aur import AURCollector
from opentrend.collectors.base import PackageCollector
from opentrend.collectors.chocolatey import ChocolateyCollector
from opentrend.collectors.crates import CratesCollector
from opentrend.collectors.distro import DistroCollector
from opentrend.collectors.go import GoCollector
from opentrend.collectors.maven import MavenCollector
from opentrend.collectors.npm import NpmCollector
from opentrend.collectors.nuget import NuGetCollector
from opentrend.collectors.packagist import PackagistCollector
from opentrend.collectors.pypi import PyPICollector
from opentrend.collectors.rubygems import RubyGemsCollector

from opentrend.distro_fetchers import FETCHERS

DISTRO_SOURCES = frozenset(FETCHERS.keys())

_PACKAGE_COLLECTORS: dict[str, type[PackageCollector]] = {
    "pypi": PyPICollector,
    "npm": NpmCollector,
    "crates_io": CratesCollector,
    "rubygems": RubyGemsCollector,
    "go": GoCollector,
    "maven": MavenCollector,
    "nuget": NuGetCollector,
    "packagist": PackagistCollector,
    "aur": AURCollector,
    "chocolatey": ChocolateyCollector,
}


def get_package_collector(
    source: str, github_token: str | None = None
) -> PackageCollector | None:
    cls = _PACKAGE_COLLECTORS.get(source)
    if cls is not None:
        return cls()
    if source in DISTRO_SOURCES:
        return DistroCollector(github_token=github_token)
    return None
