"""Shared version-fetching logic for distros, used by both discovery and the distro collector.

Each fetch function takes a niquests session and a package name, returns a dict
with "latest_version" and optionally other metrics (e.g. "downloads_monthly"), or None.
Functions that need GitHub file access take a `github_raw` callback:
    async def github_raw(owner, repo, path, ref) -> str | None
"""

import base64
import json
import re
from collections.abc import Callable, Coroutine
from typing import Any

import niquests

from opentrend import USER_AGENT
from opentrend.github_utils import GITHUB_API, GITHUB_HEADERS_BASE, github_headers
from opentrend.distro_defs import (
    ALPINE_REPOS,
    ALPINE_VERSION_RE,
    CHIMERA_SUBDIRS,
    CHIMERA_VERSION_RE,
    FREEBSD_CATEGORIES,
    FREEBSD_VERSION_RE,
    NIX_VERSION_RE,
    OPENBSD_CATEGORIES,
    OPENBSD_VERSION_PATTERNS,
    SCOOP_BUCKETS,
    SLACKBUILDS_CATEGORIES,
    SLACKBUILDS_VERSION_RE,
    TERMUX_PATH,
    TERMUX_VERSION_RE,
    VOID_PATH,
    VOID_VERSION_RE,
    WAKEMEOPS_CATEGORIES,
    WAKEMEOPS_VERSION_RE,
)

GithubRawFn = Callable[[str, str, str, str], Coroutine[Any, Any, str | None]]

_HEADERS = {"User-Agent": USER_AGENT}


def make_github_raw(
    client: niquests.AsyncSession, token: str | None = None
) -> GithubRawFn:
    """Create a github_raw callback that fetches file contents via the Contents API."""
    hdrs = github_headers(token) if token else GITHUB_HEADERS_BASE

    async def github_raw(owner: str, repo: str, path: str, ref: str) -> str | None:
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
            params={"ref": ref},
            headers=hdrs,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("encoding") == "base64":
            return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        return data.get("content")

    return github_raw


async def fetch_debian(
    client: niquests.AsyncSession, name: str, **_: Any
) -> dict | None:
    resp = await client.get(
        f"https://sources.debian.org/api/src/{name}/", headers=_HEADERS
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    versions = resp.json().get("versions", [])
    return {"latest_version": versions[0].get("version", "")} if versions else None


async def fetch_arch(client: niquests.AsyncSession, name: str, **_: Any) -> dict | None:
    resp = await client.get(
        "https://archlinux.org/packages/search/json/",
        params={"name": name},
        headers=_HEADERS,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    if not results:
        return None
    pkg = results[0]
    return {"latest_version": f"{pkg['pkgver']}-{pkg['pkgrel']}"}


async def fetch_alpine(
    _: niquests.AsyncSession, name: str, *, github_raw: GithubRawFn, **__: Any
) -> dict | None:
    for repo in ALPINE_REPOS:
        text = await github_raw(
            "alpinelinux", "aports", f"{repo}/{name}/APKBUILD", "master"
        )
        if text:
            m = re.search(ALPINE_VERSION_RE, text, re.MULTILINE)
            if m:
                return {"latest_version": m.group(1).strip()}
    return None


async def fetch_homebrew(
    client: niquests.AsyncSession, name: str, **_: Any
) -> dict | None:
    resp = await client.get(
        f"https://formulae.brew.sh/api/formula/{name}.json", headers=_HEADERS
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    data = resp.json()
    version = data.get("versions", {}).get("stable")
    if not version:
        return None
    result = {"latest_version": version}
    analytics = data.get("analytics", {})
    installs_30d = analytics.get("install_on_request", {}).get("30d", {})
    if installs_30d:
        result["downloads_monthly"] = sum(installs_30d.values())
    return result


async def fetch_homebrew_tap(
    _: niquests.AsyncSession, name: str, *, github_raw: GithubRawFn, **__: Any
) -> dict | None:
    parts = name.split("/")
    if len(parts) < 3:
        return None
    tap_user, tap_name, formula = parts[0], parts[1], parts[2]
    text = await github_raw(
        tap_user, f"homebrew-{tap_name}", f"Formula/{formula}.rb", "HEAD"
    )
    if text is None:
        text = await github_raw(
            tap_user, f"homebrew-{tap_name}", f"{formula}.rb", "HEAD"
        )
    if text is None:
        return None
    version_match = re.search(r'version\s+"([^"]+)"', text)
    if version_match:
        return {"latest_version": version_match.group(1)}
    url_match = re.search(r'url\s+"[^"]*[-/]v?(\d+\.\d+(?:\.\d+)*)', text)
    if url_match:
        return {"latest_version": url_match.group(1)}
    return None


async def fetch_macports(
    client: niquests.AsyncSession, name: str, **_: Any
) -> dict | None:
    resp = await client.get(
        f"https://ports.macports.org/api/v1/ports/{name}/", headers=_HEADERS
    )
    if resp.status_code != 200:
        return None
    return {"latest_version": resp.json().get("version", "")}


async def fetch_nix(
    _: niquests.AsyncSession, name: str, *, github_raw: GithubRawFn, **__: Any
) -> dict | None:
    text = await github_raw(
        "NixOS",
        "nixpkgs",
        f"pkgs/by-name/{name[:2]}/{name}/package.nix",
        "nixos-unstable",
    )
    if text is None:
        return None
    m = re.search(NIX_VERSION_RE, text)
    return {"latest_version": m.group(1)} if m else None


async def fetch_fedora(
    client: niquests.AsyncSession, name: str, **_: Any
) -> dict | None:
    resp = await client.get(
        "https://bodhi.fedoraproject.org/updates/",
        params={"packages": name, "rows_per_page": "1"},
        headers=_HEADERS,
    )
    if resp.status_code != 200:
        return None
    updates = resp.json().get("updates", [])
    if not updates:
        return None
    builds = updates[0].get("builds", [])
    if not builds:
        return None
    return {"latest_version": builds[0].get("nvr", "")}


async def fetch_void(
    _: niquests.AsyncSession, name: str, *, github_raw: GithubRawFn, **__: Any
) -> dict | None:
    text = await github_raw(
        "void-linux", "void-packages", VOID_PATH.format(name=name), "master"
    )
    if text is None:
        return None
    m = re.search(VOID_VERSION_RE, text, re.MULTILINE)
    return {"latest_version": m.group(1).strip()} if m else None


async def fetch_termux(
    _: niquests.AsyncSession, name: str, *, github_raw: GithubRawFn, **__: Any
) -> dict | None:
    text = await github_raw(
        "termux", "termux-packages", TERMUX_PATH.format(name=name), "master"
    )
    if text is None:
        return None
    m = re.search(TERMUX_VERSION_RE, text, re.MULTILINE)
    return {"latest_version": m.group(1).strip()} if m else None


async def fetch_chimera(
    _: niquests.AsyncSession, name: str, *, github_raw: GithubRawFn, **__: Any
) -> dict | None:
    for subdir in CHIMERA_SUBDIRS:
        text = await github_raw(
            "chimera-linux", "cports", f"{subdir}/{name}/template.py", "master"
        )
        if text:
            m = re.search(CHIMERA_VERSION_RE, text, re.MULTILINE)
            return {"latest_version": m.group(1).strip()} if m else None
    return None


async def fetch_openbsd(
    _: niquests.AsyncSession, name: str, *, github_raw: GithubRawFn, **__: Any
) -> dict | None:
    for category in OPENBSD_CATEGORIES:
        text = await github_raw(
            "openbsd", "ports", f"{category}/{name}/Makefile", "master"
        )
        if text:
            for pattern in OPENBSD_VERSION_PATTERNS:
                m = re.search(pattern, text, re.MULTILINE)
                if m:
                    return {"latest_version": m.group(1).strip()}
            return None
    return None


async def fetch_freebsd(
    _: niquests.AsyncSession, name: str, *, github_raw: GithubRawFn, **__: Any
) -> dict | None:
    for category in FREEBSD_CATEGORIES:
        text = await github_raw(
            "freebsd", "freebsd-ports", f"{category}/{name}/Makefile", "main"
        )
        if text:
            m = re.search(FREEBSD_VERSION_RE, text, re.MULTILINE)
            return {"latest_version": m.group(1).strip()} if m else None
    return None


async def fetch_gentoo(
    _: niquests.AsyncSession, name: str, *, github_raw: GithubRawFn, **__: Any
) -> dict | None:
    if "/" not in name:
        return None
    cat, pkg = name.split("/", 1)
    text = await github_raw("gentoo", "gentoo", f"{cat}/{pkg}/Manifest", "master")
    if text:
        m = re.search(rf"DIST {re.escape(pkg)}-([0-9][0-9a-zA-Z._-]*)\.", text)
        return {"latest_version": m.group(1)} if m else None
    return None


async def fetch_scoop(
    _: niquests.AsyncSession, name: str, *, github_raw: GithubRawFn, **__: Any
) -> dict | None:
    for bucket in SCOOP_BUCKETS:
        text = await github_raw(
            "ScoopInstaller", bucket, f"bucket/{name}.json", "master"
        )
        if text:
            try:
                return {"latest_version": json.loads(text).get("version", "")}
            except json.JSONDecodeError, ValueError:
                pass
    return None


async def fetch_slackbuilds(
    _: niquests.AsyncSession, name: str, *, github_raw: GithubRawFn, **__: Any
) -> dict | None:
    for category in SLACKBUILDS_CATEGORIES:
        text = await github_raw(
            "SlackBuildsOrg", "slackbuilds", f"{category}/{name}/{name}.info", "master"
        )
        if text:
            m = re.search(SLACKBUILDS_VERSION_RE, text, re.MULTILINE)
            return {"latest_version": m.group(1)} if m else None
    return None


async def fetch_opensuse(
    client: niquests.AsyncSession, name: str, **_: Any
) -> dict | None:
    resp = await client.get(
        "https://download.opensuse.org/tumbleweed/repo/oss/x86_64/", headers=_HEADERS
    )
    if resp.status_code != 200:
        return None
    m = re.search(
        rf"{re.escape(name)}-([0-9][0-9.]+)-[0-9][0-9.]*\.x86_64\.rpm", resp.text
    )
    return {"latest_version": m.group(1)} if m else None


async def fetch_manjaro(
    client: niquests.AsyncSession, name: str, **_: Any
) -> dict | None:
    mirrors = [
        "https://ftp.halifax.rwth-aachen.de/manjaro/stable/extra/x86_64/",
        "https://mirror.csclub.uwaterloo.ca/manjaro/stable/extra/x86_64/",
    ]
    for mirror in mirrors:
        try:
            resp = await client.get(mirror, headers=_HEADERS)
            if resp.status_code != 200:
                continue
            m = re.search(
                rf"{re.escape(name)}-([0-9][0-9.]+)-([0-9]+)-x86_64", resp.text
            )
            if m:
                return {"latest_version": f"{m.group(1)}-{m.group(2)}"}
        except niquests.exceptions.RequestException:
            continue
    return None


async def fetch_parabola(
    client: niquests.AsyncSession, name: str, **_: Any
) -> dict | None:
    for repo in ["extra", "core", "community", "libre"]:
        resp = await client.get(
            f"https://www.parabola.nu/packages/{repo}/x86_64/{name}/", headers=_HEADERS
        )
        if resp.status_code == 200:
            m = re.search(rf"{re.escape(name)}\s+([0-9][0-9.-]+)", resp.text)
            return {"latest_version": m.group(1)} if m else None
    return None


async def fetch_ubuntu(
    client: niquests.AsyncSession, name: str, **_: Any
) -> dict | None:
    resp = await client.get(
        "https://api.launchpad.net/1.0/ubuntu/+archive/primary",
        params={
            "ws.op": "getPublishedSources",
            "source_name": name,
            "exact_match": "true",
            "status": "Published",
        },
        headers=_HEADERS,
    )
    if resp.status_code != 200:
        return None
    entries = resp.json().get("entries", [])
    if not entries:
        return None
    return {"latest_version": entries[0].get("source_package_version", "")}


async def fetch_wakemeops(
    _: niquests.AsyncSession, name: str, *, github_raw: GithubRawFn, **__: Any
) -> dict | None:
    for category in WAKEMEOPS_CATEGORIES:
        text = await github_raw(
            "upciti", "wakemeops", f"blueprints/{category}/{name}/ops2deb.yml", "main"
        )
        if text:
            versions = re.findall(WAKEMEOPS_VERSION_RE, text, re.MULTILINE)
            return {"latest_version": versions[-1]} if versions else None
    return None


# Registry mapping source name -> fetch function
FETCHERS: dict[str, Any] = {
    "debian": fetch_debian,
    "arch": fetch_arch,
    "alpine": fetch_alpine,
    "homebrew": fetch_homebrew,
    "homebrew_tap": fetch_homebrew_tap,
    "macports": fetch_macports,
    "nix": fetch_nix,
    "fedora": fetch_fedora,
    "void": fetch_void,
    "termux": fetch_termux,
    "chimera": fetch_chimera,
    "openbsd": fetch_openbsd,
    "freebsd": fetch_freebsd,
    "gentoo": fetch_gentoo,
    "scoop": fetch_scoop,
    "slackbuilds": fetch_slackbuilds,
    "opensuse": fetch_opensuse,
    "manjaro": fetch_manjaro,
    "parabola": fetch_parabola,
    "ubuntu": fetch_ubuntu,
    "wakemeops": fetch_wakemeops,
}
