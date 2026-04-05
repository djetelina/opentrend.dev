from datetime import date
from types import SimpleNamespace

from opentrend.services.dashboard import DashboardService


def make_github_snapshot(
    d: date,
    stars: int,
    forks: int,
    *,
    open_issues: int = 10,
    closed_issues: int = 50,
    open_prs: int = 5,
    closed_prs: int = 30,
    contributors: int = 20,
    commits_total: int = 500,
    watchers: int = 100,
    dependents_repos: int | None = None,
    dependents_packages: int | None = None,
    weekly_all_commits: str | None = None,
    weekly_owner_commits: str | None = None,
    community_health: int | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        date=d,
        stars=stars,
        forks=forks,
        open_issues=open_issues,
        closed_issues=closed_issues,
        open_prs=open_prs,
        closed_prs=closed_prs,
        contributors=contributors,
        commits_total=commits_total,
        release_count=10,
        watchers=watchers,
        license="MIT",
        latest_release_date=None,
        dependents_repos=dependents_repos,
        dependents_packages=dependents_packages,
        weekly_all_commits=weekly_all_commits,
        weekly_owner_commits=weekly_owner_commits,
        community_health=community_health,
    )


def test_format_stars_series() -> None:
    snapshots = [
        make_github_snapshot(date(2026, 1, 1), 100, 10),
        make_github_snapshot(date(2026, 1, 2), 105, 12),
        make_github_snapshot(date(2026, 1, 3), 110, 15),
    ]
    series = DashboardService.format_time_series(snapshots, "stars")
    assert series == [
        {"date": "2026-01-01", "value": 100},
        {"date": "2026-01-02", "value": 105},
        {"date": "2026-01-03", "value": 110},
    ]


def test_format_packaging_matrix() -> None:
    packages = [
        SimpleNamespace(id=1, source="pypi", package_name="httpx"),
        SimpleNamespace(id=2, source="aur", package_name="python-httpx"),
        SimpleNamespace(id=3, source="debian", package_name="python3-httpx"),
    ]
    latest_snapshots = {
        1: SimpleNamespace(
            latest_version="0.27.0",
            votes=None,
            popularity=None,
            downloads_daily=None,
            downloads_weekly=None,
            downloads_monthly=None,
            downloads_total=None,
            dependents_count=None,
        ),
        2: SimpleNamespace(
            latest_version="0.27.0-1",
            votes=42,
            popularity=3.14,
            downloads_daily=None,
            downloads_weekly=None,
            downloads_monthly=None,
            downloads_total=None,
            dependents_count=None,
        ),
        3: SimpleNamespace(
            latest_version="0.25.0-1",
            votes=None,
            popularity=None,
            downloads_daily=None,
            downloads_weekly=None,
            downloads_monthly=None,
            downloads_total=None,
            dependents_count=None,
        ),
    }
    matrix = DashboardService.format_packaging_matrix(packages, latest_snapshots)
    assert len(matrix) == 3
    assert matrix[0]["source"] == "pypi"
    assert matrix[0]["version"] == "0.27.0"
    assert matrix[1]["votes"] == 42
    assert matrix[2]["version"] == "0.25.0-1"


def _make_snap_with_downloads(**kwargs) -> SimpleNamespace:
    return SimpleNamespace(
        latest_version=kwargs.get("latest_version"),
        votes=kwargs.get("votes"),
        popularity=kwargs.get("popularity"),
        downloads_daily=kwargs.get("downloads_daily"),
        downloads_weekly=kwargs.get("downloads_weekly"),
        downloads_monthly=kwargs.get("downloads_monthly"),
        downloads_total=kwargs.get("downloads_total"),
        dependents_count=kwargs.get("dependents_count"),
    )


class TestComputeReach:
    def test_returns_zero_when_no_github(self) -> None:
        assert DashboardService.compute_reach(None, [], 0) == 0

    def test_basic_computation(self) -> None:
        gh = make_github_snapshot(date(2026, 1, 1), stars=1000, forks=200)
        matrix = [{"version": "1.0.0", "dependents_count": 50}]
        score = DashboardService.compute_reach(gh, matrix, total_downloads=10000)
        assert score > 0
        assert isinstance(score, int)

    def test_zero_stats_no_crash(self) -> None:
        gh = make_github_snapshot(
            date(2026, 1, 1), stars=0, forks=0, contributors=0, watchers=0
        )
        score = DashboardService.compute_reach(gh, [], 0)
        assert score == 0 or score >= 0  # Should not crash

    def test_github_dependents_preferred(self) -> None:
        gh = make_github_snapshot(
            date(2026, 1, 1),
            stars=100,
            forks=10,
            dependents_repos=500,
            dependents_packages=100,
        )
        matrix = [{"version": "1.0", "dependents_count": 10}]
        score = DashboardService.compute_reach(gh, matrix, 0)
        # Should use gh dependents (600) not registry (10)
        gh_no_deps = make_github_snapshot(date(2026, 1, 1), stars=100, forks=10)
        score_registry = DashboardService.compute_reach(gh_no_deps, matrix, 0)
        assert score > score_registry

    def test_traffic_contributes(self) -> None:
        gh = make_github_snapshot(date(2026, 1, 1), stars=100, forks=10)
        score_no_traffic = DashboardService.compute_reach(gh, [], 0)
        score_with_traffic = DashboardService.compute_reach(
            gh, [], 0, traffic_views=10000, traffic_clones=5000
        )
        assert score_with_traffic > score_no_traffic


class TestComputeGithubDeltas:
    def test_both_snapshots(self) -> None:
        latest = make_github_snapshot(date(2026, 1, 7), stars=110, forks=15)
        week_ago = make_github_snapshot(date(2026, 1, 1), stars=100, forks=10)
        deltas = DashboardService.compute_github_deltas(latest, week_ago)
        assert deltas["stars_delta"] == 10
        assert deltas["forks_delta"] == 5

    def test_latest_none(self) -> None:
        assert DashboardService.compute_github_deltas(None, SimpleNamespace()) == {}

    def test_week_ago_none(self) -> None:
        assert DashboardService.compute_github_deltas(SimpleNamespace(), None) == {}

    def test_both_none(self) -> None:
        assert DashboardService.compute_github_deltas(None, None) == {}

    def test_negative_deltas(self) -> None:
        latest = make_github_snapshot(date(2026, 1, 7), stars=90, forks=8)
        week_ago = make_github_snapshot(date(2026, 1, 1), stars=100, forks=10)
        deltas = DashboardService.compute_github_deltas(latest, week_ago)
        assert deltas["stars_delta"] == -10
        assert deltas["forks_delta"] == -2


class TestComputeTotalDownloads:
    def test_monthly_preferred(self) -> None:
        matrix = [
            {"downloads_monthly": 1000, "downloads_daily": 50},
            {"downloads_monthly": 2000, "downloads_daily": None},
        ]
        assert DashboardService.compute_total_downloads(matrix) == 3000

    def test_daily_fallback(self) -> None:
        matrix = [{"downloads_monthly": None, "downloads_daily": 100}]
        assert DashboardService.compute_total_downloads(matrix) == 3000

    def test_empty_matrix(self) -> None:
        assert DashboardService.compute_total_downloads([]) == 0

    def test_none_values(self) -> None:
        matrix = [{"downloads_monthly": None, "downloads_daily": None}]
        assert DashboardService.compute_total_downloads(matrix) == 0


class TestFormatPackagingMatrixFreshness:
    def test_current_version(self) -> None:
        pkg = SimpleNamespace(id=1, source="pypi", package_name="httpx")
        snap = _make_snap_with_downloads(latest_version="0.27.0")
        matrix = DashboardService.format_packaging_matrix(
            [pkg], {pkg.id: snap}, "v0.27.0"
        )
        assert matrix[0]["freshness"] == "current"

    def test_outdated_version(self) -> None:
        pkg = SimpleNamespace(id=2, source="debian", package_name="python3-httpx")
        snap = _make_snap_with_downloads(latest_version="0.25.0-1")
        matrix = DashboardService.format_packaging_matrix(
            [pkg], {pkg.id: snap}, "v0.27.0"
        )
        assert matrix[0]["freshness"] == "outdated"

    def test_underscore_normalization(self) -> None:
        pkg = SimpleNamespace(id=3, source="arch", package_name="curl")
        snap = _make_snap_with_downloads(latest_version="8_19_0")
        matrix = DashboardService.format_packaging_matrix(
            [pkg], {pkg.id: snap}, "curl-8.19.0"
        )
        assert matrix[0]["freshness"] == "current"

    def test_no_release_tag(self) -> None:
        pkg = SimpleNamespace(id=1, source="pypi", package_name="httpx")
        snap = _make_snap_with_downloads(latest_version="0.27.0")
        matrix = DashboardService.format_packaging_matrix([pkg], {pkg.id: snap}, None)
        assert matrix[0]["freshness"] == "unknown"

    def test_no_snapshot(self) -> None:
        pkg = SimpleNamespace(id=1, source="pypi", package_name="httpx")
        matrix = DashboardService.format_packaging_matrix([pkg], {}, "v1.0.0")
        assert matrix[0]["freshness"] == "unknown"
        assert matrix[0]["version"] is None

    def test_unparseable_version(self) -> None:
        pkg = SimpleNamespace(id=4, source="gentoo", package_name="dev-util/foo")
        snap = _make_snap_with_downloads(latest_version="git-HEAD")
        matrix = DashboardService.format_packaging_matrix(
            [pkg], {pkg.id: snap}, "v1.0.0"
        )
        assert matrix[0]["freshness"] == "unknown"


class TestSummarizeReleases:
    def test_keeps_latest_per_asset(self) -> None:
        dl1 = SimpleNamespace(
            release_tag="v1.0",
            asset_name="app.tar.gz",
            download_count=100,
            date=date(2026, 1, 1),
        )
        dl2 = SimpleNamespace(
            release_tag="v1.0",
            asset_name="app.tar.gz",
            download_count=150,
            date=date(2026, 1, 2),
        )
        result = DashboardService.summarize_releases([dl1, dl2])
        assert len(result) == 1
        assert result[0]["total_downloads"] == 150

    def test_empty_input(self) -> None:
        assert DashboardService.summarize_releases([]) == []

    def test_multiple_releases(self) -> None:
        dl1 = SimpleNamespace(
            release_tag="v1.0",
            asset_name="app.tar.gz",
            download_count=100,
            date=date(2026, 1, 1),
        )
        dl2 = SimpleNamespace(
            release_tag="v2.0",
            asset_name="app.tar.gz",
            download_count=50,
            date=date(2026, 1, 2),
        )
        result = DashboardService.summarize_releases([dl1, dl2])
        assert len(result) == 2
