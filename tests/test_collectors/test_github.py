import pytest

from opentrend.collectors.base import ProjectCollector
from opentrend.collectors.github import GithubCollector


def test_github_collector_implements_protocol() -> None:
    assert issubclass(GithubCollector, ProjectCollector)


@pytest.fixture()
def repo_response() -> dict:
    return {
        "stargazers_count": 12500,
        "forks_count": 890,
        "open_issues_count": 45,
        "subscribers_count": 300,
        "license": {"spdx_id": "BSD-3-Clause"},
    }


@pytest.fixture()
def issues_response() -> list[dict]:
    return [{"state": "closed"}] * 200


@pytest.fixture()
def pulls_response() -> list[dict]:
    return [{"state": "open"}] * 10


@pytest.fixture()
def contributors_response() -> list[dict]:
    return [{"id": i} for i in range(150)]


@pytest.fixture()
def releases_response() -> list[dict]:
    return [
        {
            "tag_name": "v0.27.0",
            "published_at": "2024-06-01T00:00:00Z",
            "assets": [
                {"name": "dist.tar.gz", "download_count": 5000},
            ],
        },
        {
            "tag_name": "v0.26.0",
            "published_at": "2024-03-01T00:00:00Z",
            "assets": [],
        },
    ]


@pytest.fixture()
def commits_response() -> list[dict]:
    return [{"sha": f"abc{i}"} for i in range(30)]


@pytest.mark.asyncio
async def test_github_collector_parses_repo_data(repo_response: dict) -> None:
    collector = GithubCollector(token="fake-token")
    data = collector.parse_repo(repo_response)
    assert data["stars"] == 12500
    assert data["forks"] == 890
    assert data["watchers"] == 300
    assert data["license"] == "BSD-3-Clause"


@pytest.mark.asyncio
async def test_github_collector_parses_releases(releases_response: list[dict]) -> None:
    collector = GithubCollector(token="fake-token")
    release_data = collector.parse_releases(releases_response)
    assert release_data["release_count"] == 2
    assert release_data["latest_release_date"] is not None
    assert len(release_data["assets"]) == 1
    assert release_data["assets"][0]["download_count"] == 5000
