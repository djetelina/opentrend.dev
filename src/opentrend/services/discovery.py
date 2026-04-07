import asyncio
import logging
import re
from collections import Counter
from dataclasses import dataclass
from xml.etree.ElementTree import ParseError

from defusedxml.ElementTree import fromstring as defused_fromstring

import niquests
from packaging.version import InvalidVersion, Version

from opentrend import USER_AGENT
from opentrend.distro_fetchers import FETCHERS, GithubRawFn, make_github_raw
from opentrend.metrics import instrumented_client

logger = logging.getLogger(__name__)

_ATOM_NS = {
    "a": "http://www.w3.org/2005/Atom",
    "d": "http://schemas.microsoft.com/ado/2007/08/dataservices",
    "m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
}


@dataclass(frozen=True)
class DiscoveredPackage:
    source: str
    package_name: str
    version: str


@dataclass
class DiscoveryResult:
    packages: list[DiscoveredPackage]
    warnings: list[str]


# ── Distro discovery wrapper ──
# Uses shared fetchers from distro_fetchers.py, with candidate name expansion.

# Sources where discovery tries multiple candidate names
_CANDIDATES = {
    "arch": lambda name: [name, f"python-{name}"],
    "alpine": lambda name: [name, f"py3-{name}"],
    "debian": lambda name: [name, f"python3-{name}"],
    "fedora": lambda name: [name, f"python-{name}"],
}


async def _discover_distro(
    client: niquests.AsyncSession,
    source: str,
    name: str,
    github_raw: GithubRawFn,
) -> list[DiscoveredPackage]:
    """Use shared fetcher for a single distro source, with candidate name expansion."""
    fetcher = FETCHERS.get(source)
    if fetcher is None:
        return []

    candidates_fn = _CANDIDATES.get(source)
    candidates = candidates_fn(name) if candidates_fn else [name]

    packages = []
    for candidate in candidates:
        try:
            result = await fetcher(client, candidate, github_raw=github_raw)
        except niquests.exceptions.RequestException, KeyError, ValueError, TypeError:
            logger.warning(
                "Discovery failed for %s:%s", source, candidate, exc_info=True
            )
            continue
        if result:
            packages.append(
                DiscoveredPackage(
                    source,
                    candidate,
                    result["latest_version"],
                )
            )
    return packages


# ── Registry checks (not shared with distro collector — dedicated collectors exist) ──


async def _check_pypi(
    client: niquests.AsyncSession, name: str
) -> DiscoveredPackage | None:
    resp = await client.get(f"https://pypi.org/pypi/{name}/json")
    if resp.status_code != 200:
        return None
    data = resp.json()
    return DiscoveredPackage(
        "pypi", data["info"]["name"].lower(), data["info"]["version"]
    )


async def _check_npm(
    client: niquests.AsyncSession, name: str
) -> DiscoveredPackage | None:
    resp = await client.get(f"https://registry.npmjs.org/{name}/latest")
    if resp.status_code != 200:
        return None
    data = resp.json()
    return DiscoveredPackage(
        "npm", data.get("name", name).lower(), data.get("version", "")
    )


async def _check_crates(
    client: niquests.AsyncSession, name: str
) -> DiscoveredPackage | None:
    resp = await client.get(
        f"https://crates.io/api/v1/crates/{name}",
        headers={"User-Agent": USER_AGENT},
    )
    if resp.status_code != 200:
        return None
    data = resp.json()
    return DiscoveredPackage("crates_io", name, data["crate"]["max_version"])


async def _check_rubygems(
    client: niquests.AsyncSession, name: str
) -> DiscoveredPackage | None:
    resp = await client.get(f"https://rubygems.org/api/v1/gems/{name}.json")
    if resp.status_code != 200:
        return None
    data = resp.json()
    return DiscoveredPackage(
        "rubygems", data.get("name", name).lower(), data["version"]
    )


async def _check_packagist(
    client: niquests.AsyncSession, name: str
) -> DiscoveredPackage | None:
    resp = await client.get(f"https://packagist.org/packages/{name}/{name}.json")
    if resp.status_code != 200:
        return None
    pkg = resp.json().get("package", {})
    versions = pkg.get("versions", {})
    stable = [k for k in versions if not k.startswith("dev-")]
    version = stable[0] if stable else ""
    return DiscoveredPackage("packagist", f"{name}/{name}", version)


async def _check_nuget(
    client: niquests.AsyncSession, name: str
) -> DiscoveredPackage | None:
    resp = await client.get(
        "https://api.nuget.org/v3/query",
        params={"q": name, "take": 5},
    )
    if resp.status_code != 200:
        return None
    for entry in resp.json().get("data", []):
        if entry.get("id", "").lower() == name.lower():
            return DiscoveredPackage("nuget", entry["id"], entry.get("version", ""))
    return None


async def _check_aur(
    client: niquests.AsyncSession, name: str
) -> list[DiscoveredPackage]:
    expected = {
        name,
        f"{name}-git",
        f"{name}-bin",
        f"python-{name}",
        f"python-{name}-git",
        f"ruby-{name}",
        f"nodejs-{name}",
        f"rust-{name}",
    }

    search_resp = await client.get(
        "https://aur.archlinux.org/rpc/v5/search",
        params={"arg": name, "by": "name"},
    )
    search_results = []
    if search_resp.status_code == 200:
        search_results = search_resp.json().get("results", [])

    found_names = {r["Name"] for r in search_results}
    missing = expected - found_names
    if missing:
        info_resp = await client.get(
            "https://aur.archlinux.org/rpc/v5/info",
            params=[("arg[]", n) for n in missing],
        )
        if info_resp.status_code == 200:
            search_results.extend(info_resp.json().get("results", []))

    packages = []
    for r in search_results:
        pkg_name = r["Name"]
        if pkg_name in expected:
            version = "HEAD" if pkg_name.endswith("-git") else r["Version"]
            packages.append(DiscoveredPackage("aur", pkg_name, version))
    return packages


async def _check_homebrew(
    client: niquests.AsyncSession, name: str
) -> DiscoveredPackage | None:
    resp = await client.get(f"https://formulae.brew.sh/api/formula/{name}.json")
    if resp.status_code != 200:
        return None
    data = resp.json()
    version = data.get("versions", {}).get("stable", "")
    return DiscoveredPackage("homebrew", name, version) if version else None


async def _check_chocolatey(
    client: niquests.AsyncSession, name: str
) -> DiscoveredPackage | None:
    resp = await client.get(
        f"https://community.chocolatey.org/api/v2/FindPackagesById()?id=%27{name}%27&$top=1&$orderby=Version%20desc",
    )
    if resp.status_code != 200:
        return None
    try:
        root = defused_fromstring(resp.text)
        for entry in root.findall("a:entry", _ATOM_NS):
            props = entry.find("m:properties", _ATOM_NS)
            if props is None:
                continue
            version_el = props.find("d:Version", _ATOM_NS)
            if version_el is not None and version_el.text:
                return DiscoveredPackage("chocolatey", name, version_el.text)
    except ParseError, KeyError, ValueError, TypeError:
        logger.warning("Chocolatey XML parse failed for %s", name, exc_info=True)
    return None


async def _check_gentoo(
    client: niquests.AsyncSession, name: str, github_raw: GithubRawFn
) -> DiscoveredPackage | None:
    """Gentoo discovery searches packages.gentoo.org first to find the category."""
    resp = await client.get(
        f"https://packages.gentoo.org/packages/search?q={name}",
        allow_redirects=True,
    )
    if resp.status_code != 200:
        return None
    matches = re.findall(r'href="/packages/([a-z0-9-]+/[a-z0-9A-Z_+-]+)"', resp.text)
    candidates = [m for m in matches if name in m.split("/")[-1]]
    if not candidates:
        return None
    cat_pkg = candidates[0]
    cat, pkg_name = cat_pkg.split("/", 1)

    text = await github_raw("gentoo", "gentoo", f"{cat}/{pkg_name}/Manifest", "master")
    if not text:
        return None
    versions = re.findall(
        rf"DIST (?:{re.escape(pkg_name)}|{re.escape(name)})-([0-9][0-9a-zA-Z._]*?)(?:-(?:deps|vendor))?\.tar",
        text,
    )
    if versions:

        def _ver_key(v: str) -> Version:
            try:
                return Version(v)
            except InvalidVersion:
                return Version("0")

        version = max(versions, key=_ver_key)
    else:
        version = ""
    return DiscoveredPackage("gentoo", f"{cat}/{pkg_name}", version)


# ── Main ──


async def discover(
    project_name: str, github_token: str | None = None
) -> DiscoveryResult:
    """Discover packages across registries and distros."""
    async with instrumented_client(
        timeout=10.0, headers={"User-Agent": USER_AGENT}
    ) as client:
        github_raw = make_github_raw(client, github_token)

        tasks = [
            # Registries
            _check_pypi(client, project_name),
            _check_npm(client, project_name),
            _check_crates(client, project_name),
            _check_rubygems(client, project_name),
            _check_packagist(client, project_name),
            _check_nuget(client, project_name),
            # Arch
            _discover_distro(client, "arch", project_name, github_raw),
            _check_aur(client, project_name),
            # macOS
            _check_homebrew(client, project_name),
            _discover_distro(client, "macports", project_name, github_raw),
            # Windows
            _check_chocolatey(client, project_name),
            _discover_distro(client, "scoop", project_name, github_raw),
            # Debian/Ubuntu
            _discover_distro(client, "debian", project_name, github_raw),
            _discover_distro(client, "ubuntu", project_name, github_raw),
            # RPM
            _discover_distro(client, "fedora", project_name, github_raw),
            # Other distros (all use shared fetchers)
            _discover_distro(client, "nix", project_name, github_raw),
            _discover_distro(client, "alpine", project_name, github_raw),
            _discover_distro(client, "void", project_name, github_raw),
            _discover_distro(client, "termux", project_name, github_raw),
            _discover_distro(client, "chimera", project_name, github_raw),
            _discover_distro(client, "openbsd", project_name, github_raw),
            _discover_distro(client, "freebsd", project_name, github_raw),
            _check_gentoo(client, project_name, github_raw),
            _discover_distro(client, "slackbuilds", project_name, github_raw),
            _discover_distro(client, "opensuse", project_name, github_raw),
            _discover_distro(client, "manjaro", project_name, github_raw),
            _discover_distro(client, "parabola", project_name, github_raw),
            _discover_distro(client, "wakemeops", project_name, github_raw),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        packages = []
        for result in results:
            if isinstance(result, BaseException):
                logger.warning("Discovery task failed: %s", result)
                continue
            if result is None:
                continue
            if isinstance(result, list):
                packages.extend(result)
            else:
                packages.append(result)

        return _filter_outliers(packages)


def _parse_major(version: str) -> int | None:
    try:
        return Version(version.lstrip("vV").split("-")[0]).major
    except InvalidVersion:
        return None


def _filter_outliers(packages: list[DiscoveredPackage]) -> DiscoveryResult:
    """Remove packages whose major version disagrees with the majority."""
    if len(packages) < 3:
        return DiscoveryResult(packages=packages, warnings=[])

    majors = Counter(m for p in packages if (m := _parse_major(p.version)) is not None)
    if not majors:
        return DiscoveryResult(packages=packages, warnings=[])

    consensus = majors.most_common(1)[0][0]
    filtered = []
    warnings = []
    for p in packages:
        m = _parse_major(p.version)
        if m is not None and m != consensus:
            warnings.append(
                f"Excluded {p.source}:{p.package_name} v{p.version} "
                f"(major {m} vs consensus {consensus})"
            )
        else:
            filtered.append(p)

    return DiscoveryResult(packages=filtered, warnings=warnings)
