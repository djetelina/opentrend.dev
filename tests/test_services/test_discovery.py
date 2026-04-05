import json as json_mod
from unittest.mock import AsyncMock

import niquests
import pytest

from opentrend.services.discovery import (
    _check_pypi,
    _check_npm,
    _check_crates,
    _check_rubygems,
    _check_aur,
    _check_homebrew,
    _check_chocolatey,
    _discover_distro,
)
from opentrend.distro_fetchers import (
    fetch_debian,
    fetch_arch,
    fetch_alpine,
    fetch_fedora,
    fetch_nix,
    fetch_void,
)


def _make_response(status_code: int, data: dict | str | list) -> niquests.Response:
    resp = niquests.Response()
    resp.status_code = status_code
    if isinstance(data, str):
        resp._content = data.encode()
    else:
        resp._content = json_mod.dumps(data).encode()
        resp.headers["Content-Type"] = "application/json"
    return resp


def _mock_client(responses: dict[str, tuple[int, dict | str | list]]) -> AsyncMock:
    """Create a mock niquests session that returns responses based on URL substring matching."""
    client = AsyncMock()

    async def _get(url, **kwargs):
        for pattern, (status, data) in responses.items():
            if pattern in str(url):
                return _make_response(status, data)
        return _make_response(404, "")

    client.get = _get
    return client


def _mock_github_raw(responses: dict[str, str]):
    """Create a mock github_raw callback."""

    async def github_raw(owner: str, repo: str, path: str, ref: str) -> str | None:
        key = f"{owner}/{repo}/{path}"
        for pattern, text in responses.items():
            if pattern in key:
                return text
        return None

    return github_raw


# ── Registry checks ──


@pytest.mark.asyncio
async def test_check_pypi_found() -> None:
    client = _mock_client(
        {
            "pypi.org": (200, {"info": {"name": "requests", "version": "2.31.0"}}),
        }
    )
    result = await _check_pypi(client, "requests")
    assert result is not None
    assert result.source == "pypi"
    assert result.package_name == "requests"
    assert result.version == "2.31.0"


@pytest.mark.asyncio
async def test_check_pypi_not_found() -> None:
    client = _mock_client({"pypi.org": (404, {})})
    result = await _check_pypi(client, "nonexistent-package-xyz")
    assert result is None


@pytest.mark.asyncio
async def test_check_npm_found() -> None:
    client = _mock_client(
        {
            "registry.npmjs.org": (200, {"name": "express", "version": "4.18.2"}),
        }
    )
    result = await _check_npm(client, "express")
    assert result is not None
    assert result.source == "npm"
    assert result.version == "4.18.2"


@pytest.mark.asyncio
async def test_check_npm_not_found() -> None:
    client = _mock_client({"registry.npmjs.org": (404, {})})
    result = await _check_npm(client, "nope")
    assert result is None


@pytest.mark.asyncio
async def test_check_crates_found() -> None:
    client = _mock_client(
        {
            "crates.io": (200, {"crate": {"name": "serde", "max_version": "1.0.195"}}),
        }
    )
    result = await _check_crates(client, "serde")
    assert result is not None
    assert result.source == "crates_io"
    assert result.version == "1.0.195"


@pytest.mark.asyncio
async def test_check_rubygems_found() -> None:
    client = _mock_client(
        {
            "rubygems.org": (200, {"name": "rails", "version": "7.1.2"}),
        }
    )
    result = await _check_rubygems(client, "rails")
    assert result is not None
    assert result.source == "rubygems"
    assert result.version == "7.1.2"


@pytest.mark.asyncio
async def test_check_aur_found() -> None:
    client = _mock_client(
        {
            "aur.archlinux.org/rpc": (
                200,
                {
                    "results": [
                        {"Name": "chezmoi-bin", "Version": "2.42.0-1"},
                        {"Name": "chezmoi-git", "Version": "r1234-1"},
                    ]
                },
            ),
        }
    )
    result = await _check_aur(client, "chezmoi")
    assert len(result) >= 1
    assert all(r.source == "aur" for r in result)


@pytest.mark.asyncio
async def test_check_homebrew_found() -> None:
    client = _mock_client(
        {
            "formulae.brew.sh": (
                200,
                {
                    "name": "curl",
                    "versions": {"stable": "8.5.0"},
                },
            ),
        }
    )
    result = await _check_homebrew(client, "curl")
    assert result is not None
    assert result.source == "homebrew"
    assert result.version == "8.5.0"


@pytest.mark.asyncio
async def test_check_chocolatey_found() -> None:
    atom_xml = """<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom"
          xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices"
          xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata">
        <entry>
            <m:properties>
                <d:Version>8.5.0</d:Version>
                <d:IsLatestVersion m:type="Edm.Boolean">true</d:IsLatestVersion>
                <d:DownloadCount m:type="Edm.Int32">100000</d:DownloadCount>
            </m:properties>
        </entry>
    </feed>"""
    client = _mock_client(
        {
            "chocolatey.org": (200, atom_xml),
        }
    )
    result = await _check_chocolatey(client, "curl")
    assert result is not None
    assert result.source == "chocolatey"


# ── Shared fetcher tests (via _discover_distro or direct) ──


@pytest.mark.asyncio
async def test_fetch_arch_found() -> None:
    client = _mock_client(
        {
            "archlinux.org/packages/search": (
                200,
                {
                    "results": [
                        {
                            "pkgname": "curl",
                            "pkgver": "8.5.0",
                            "pkgrel": "1",
                            "repo": "core",
                        }
                    ]
                },
            ),
        }
    )
    result = await fetch_arch(client, "curl")
    assert result is not None
    assert result["latest_version"] == "8.5.0-1"


@pytest.mark.asyncio
async def test_fetch_debian_found() -> None:
    client = _mock_client(
        {
            "sources.debian.org": (
                200,
                {
                    "versions": [
                        {"version": "8.5.0-1", "suites": ["sid"]},
                    ]
                },
            ),
        }
    )
    result = await fetch_debian(client, "curl")
    assert result is not None
    assert result["latest_version"] == "8.5.0-1"


@pytest.mark.asyncio
async def test_fetch_alpine_found() -> None:
    gh_raw = _mock_github_raw(
        {
            "alpinelinux/aports": "pkgname=curl\npkgver=8.5.0\npkgrel=1\n",
        }
    )
    client = _mock_client({})
    result = await fetch_alpine(client, "curl", github_raw=gh_raw)
    assert result is not None
    assert result["latest_version"] == "8.5.0"


@pytest.mark.asyncio
async def test_fetch_nix_found() -> None:
    gh_raw = _mock_github_raw(
        {
            "NixOS/nixpkgs": 'stdenv.mkDerivation rec {\n  pname = "curl";\n  version = "8.5.0";\n}',
        }
    )
    client = _mock_client({})
    result = await fetch_nix(client, "curl", github_raw=gh_raw)
    assert result is not None
    assert result["latest_version"] == "8.5.0"


@pytest.mark.asyncio
async def test_fetch_void_found() -> None:
    gh_raw = _mock_github_raw(
        {
            "void-linux/void-packages": "pkgname=curl\nversion=8.5.0\nrevision=1\n",
        }
    )
    client = _mock_client({})
    result = await fetch_void(client, "curl", github_raw=gh_raw)
    assert result is not None
    assert result["latest_version"] == "8.5.0"


@pytest.mark.asyncio
async def test_discover_distro_with_candidates() -> None:
    """Discovery tries candidate names (e.g. debian tries name + python3-name)."""
    client = _mock_client(
        {
            "sources.debian.org": (200, {"versions": [{"version": "1.0"}]}),
        }
    )
    gh_raw = _mock_github_raw({})
    result = await _discover_distro(client, "debian", "mylib", gh_raw)
    # Should find both "mylib" and "python3-mylib" since mock matches any URL
    assert len(result) >= 1
    assert all(r.source == "debian" for r in result)


@pytest.mark.asyncio
async def test_fetch_fedora_found() -> None:
    client = _mock_client(
        {
            "bodhi.fedoraproject.org": (
                200,
                {
                    "updates": [{"builds": [{"nvr": "curl-8.5.0-1.fc39"}]}],
                },
            ),
        }
    )
    result = await fetch_fedora(client, "curl")
    assert result is not None
    assert result["latest_version"] == "curl-8.5.0-1.fc39"
