import json
from datetime import date, datetime, timedelta, timezone

from packaging.version import InvalidVersion, Version

from litestar import Controller, get
from litestar.connection import Request
from litestar.exceptions import NotFoundException
from litestar.response import Redirect, Template
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opentrend.models.project import Project
from opentrend.models.snapshot import GithubSnapshot
from opentrend.models.user import User
from opentrend.routes import require_login
from opentrend.services.dashboard import DashboardService
from opentrend.types import NamedSeries, ReleaseAsset, ReleaseSummary

# Time range presets: (label, days for daily charts, weeks for weekly stats charts)
TIME_RANGES = {
    "30d": {"label": "30d", "days": 30, "weeks": 8},
    "90d": {"label": "90d", "days": 90, "weeks": 13},
    "1y": {"label": "1y", "days": 365, "weeks": 52},
}
DEFAULT_RANGE = "30d"


_ARTIFACT_EXTENSIONS = frozenset(
    {".deb", ".rpm", ".msi", ".exe", ".dmg", ".pkg", ".appimage", ".snap", ".flatpak"}
)

# GitHub snapshot fields that map 1:1 to chart series context keys
_GH_SERIES_FIELDS = [
    ("stars", "stars_series"),
    ("forks", "forks_series"),
    ("closed_issues", "closed_issues_series"),
    ("open_prs", "prs_series"),
    ("closed_prs", "closed_prs_series"),
    ("contributors", "contributors_series"),
    ("commits_total", "commits_series"),
    ("release_count", "release_count_series"),
    ("watchers", "watchers_series"),
    ("reach_score", "reach_series"),
]


def _json_script(obj) -> str:
    """Serialize to JSON safe for embedding in <script> tags.

    Escapes </script> sequences that could break out of a script context.
    """
    return json.dumps(obj).replace("</", r"<\/")


def _detect_artifact_types(assets: list[ReleaseAsset]) -> list[str]:
    """Extract human-readable artifact types from release asset names."""
    seen: set[str] = set()
    types: list[str] = []
    for asset in assets:
        name = asset["asset_name"].lower()
        # .apk needs special handling to exclude .apk.asc
        if name.endswith(".apk") and not name.endswith(".apk.asc"):
            label = ".apk"
        else:
            label = next(
                (ext for ext in _ARTIFACT_EXTENSIONS if name.endswith(ext)),
                None,
            )
        if label:
            display = ".AppImage" if label == ".appimage" else label
            if display not in seen:
                seen.add(display)
                types.append(display)
    return types


def _format_release_ago(latest_gh) -> str | None:
    """Format relative time for latest release."""
    if not latest_gh or not latest_gh.latest_release_date:
        return None
    days = (
        datetime.now(timezone.utc).date() - latest_gh.latest_release_date.date()
    ).days
    if days == 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 30:
        return f"{days}d ago"
    if days < 365:
        return f"{days // 30}mo ago"
    return f"{days // 365}y ago"


def _compute_next_scan(project_id) -> tuple[str, str]:
    """Compute scan timing info. Returns (next_scan_utc, next_scan_in)."""
    from opentrend.scheduler.jobs import compute_collection_hour

    hour = compute_collection_hour(project_id)
    now = datetime.now(timezone.utc)
    today_scan = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    next_scan = today_scan if now < today_scan else today_scan + timedelta(days=1)

    total_seconds = (next_scan - now).total_seconds()
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    next_scan_in = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
    return next_scan.strftime("%H:%M UTC"), next_scan_in


def _strip_thin_series(series: list[NamedSeries]) -> list[NamedSeries]:
    """Remove series where every data point value is 0."""
    return [s for s in series if any(d.get("value", 0) != 0 for d in s.get("data", []))]


# ── Context builders ──
# Each returns a dict of template context keys (values pre-serialized via _json_script).


def _build_github_series(
    github_snapshots: list[GithubSnapshot], weekly_weeks: int
) -> dict:
    """Build all GitHub-derived chart series."""
    fmt = DashboardService.format_time_series
    latest_gh = github_snapshots[-1] if github_snapshots else None

    ctx = {}
    for field, key in _GH_SERIES_FIELDS:
        ctx[key] = _json_script(fmt(github_snapshots, field))

    # open_issues is special: open_issues minus open_prs
    ctx["open_issues_series"] = _json_script(
        [
            {
                "date": s.date.isoformat(),
                "value": (s.open_issues or 0) - (s.open_prs or 0),
            }
            for s in github_snapshots
        ]
    )

    # Weekly stats from latest snapshot (trimmed to range)
    ctx["weekly_commits_series"] = _json_script(
        DashboardService.parse_weekly_commits(latest_gh, weeks=weekly_weeks)
    )
    additions, deletions = DashboardService.parse_code_frequency(
        latest_gh, weeks=weekly_weeks
    )
    ctx["additions_series"] = _json_script(additions)
    ctx["deletions_series"] = _json_script(deletions)
    owner, community = DashboardService.parse_participation(
        latest_gh, weeks=weekly_weeks
    )
    ctx["owner_commits_series"] = _json_script(owner)
    ctx["community_commits_series"] = _json_script(community)

    return ctx


def _build_package_series(
    project: Project,
    snaps_by_mapping: dict,
    github_snapshots: list[GithubSnapshot],
) -> dict:
    """Build download, dependents, and AUR chart series from package snapshots."""
    fmt = DashboardService.format_time_series
    download_series = []
    dependents_series = []
    aur_votes_series: list = []
    aur_popularity_series: list = []

    for mapping in project.package_mappings:
        pkg_snaps = snaps_by_mapping.get(mapping.id, [])
        if not pkg_snaps:
            continue

        series_name = f"{mapping.source}:{mapping.package_name}"

        # Downloads: prefer daily > monthly > total (as daily deltas)
        has_daily = any(s.downloads_daily for s in pkg_snaps)
        has_monthly = any(s.downloads_monthly for s in pkg_snaps)
        has_total = any(s.downloads_total for s in pkg_snaps)
        if has_daily:
            download_series.append(
                {"name": series_name, "data": fmt(pkg_snaps, "downloads_daily")}
            )
        elif has_monthly:
            download_series.append(
                {"name": series_name, "data": fmt(pkg_snaps, "downloads_monthly")}
            )
        elif has_total:
            dl_deltas = []
            for i in range(1, len(pkg_snaps)):
                prev = pkg_snaps[i - 1].downloads_total or 0
                curr = pkg_snaps[i].downloads_total or 0
                dl_deltas.append(
                    {
                        "date": pkg_snaps[i].date.isoformat(),
                        "value": max(0, curr - prev),
                    }
                )
            if dl_deltas:
                download_series.append(
                    {"name": f"{series_name} (daily delta)", "data": dl_deltas}
                )

        # Dependents over time
        if any(s.dependents_count for s in pkg_snaps):
            dependents_series.append(
                {
                    "name": series_name,
                    "data": [
                        {"date": s.date.isoformat(), "value": s.dependents_count or 0}
                        for s in pkg_snaps
                    ],
                }
            )

        # AUR-specific
        if mapping.source == "aur" and any(s.votes is not None for s in pkg_snaps):
            aur_votes_series = fmt(pkg_snaps, "votes")
            aur_popularity_series = fmt(pkg_snaps, "popularity")

    # GitHub dependents as additional dependents series
    for field, label in [
        ("dependents_repos", "github:repos"),
        ("dependents_packages", "github:packages"),
    ]:
        data = [
            {"date": s.date.isoformat(), "value": getattr(s, field) or 0}
            for s in github_snapshots
            if getattr(s, field) is not None
        ]
        if data and any(d["value"] > 0 for d in data):
            dependents_series.append({"name": label, "data": data})

    return {
        "download_series": _json_script(_strip_thin_series(download_series)),
        "dependents_series": _json_script(_strip_thin_series(dependents_series)),
        "aur_votes_series": _json_script(aur_votes_series),
        "aur_popularity_series": _json_script(aur_popularity_series),
    }


def _build_release_context(release_downloads: list) -> dict:
    """Build release summary, download series, and artifact types."""
    download_series_entry = None

    if release_downloads:
        totals_by_date: dict[date, int] = {}
        for dl in release_downloads:
            totals_by_date[dl.date] = totals_by_date.get(dl.date, 0) + dl.download_count
        sorted_dates = sorted(totals_by_date.keys())
        if len(sorted_dates) >= 2:
            gh_dl_deltas = [
                {
                    "date": sorted_dates[i].isoformat(),
                    "value": max(
                        0,
                        totals_by_date[sorted_dates[i]]
                        - totals_by_date[sorted_dates[i - 1]],
                    ),
                }
                for i in range(1, len(sorted_dates))
            ]
            if gh_dl_deltas:
                download_series_entry = {
                    "name": "github releases",
                    "data": gh_dl_deltas,
                }

    release_summary = DashboardService.summarize_releases(release_downloads)

    def _version_key(r: ReleaseSummary) -> Version:
        tag = r["release_tag"].lstrip("vV")
        try:
            return Version(tag)
        except InvalidVersion:
            return Version("0")

    release_summary.sort(key=_version_key)
    release_summary = release_summary[-4:]

    release_artifact_types = (
        _detect_artifact_types(release_summary[-1].get("assets", []))
        if release_summary
        else []
    )

    return {
        "release_download_entry": download_series_entry,
        "release_summary": release_summary,
        "release_download_series": _json_script(
            [
                {"name": r["release_tag"], "downloads": r["total_downloads"]}
                for r in release_summary
            ]
        ),
        "release_artifact_types": release_artifact_types,
    }


def _build_traffic_context(traffic_snapshots: list, traffic_referrers: list) -> dict:
    """Build all traffic chart series and referrer table."""
    fmt = DashboardService.format_time_series
    return {
        "clones_series": _json_script(fmt(traffic_snapshots, "clones")),
        "unique_clones_series": _json_script(fmt(traffic_snapshots, "unique_clones")),
        "traffic_views_series": _json_script(fmt(traffic_snapshots, "views")),
        "unique_views_series": _json_script(fmt(traffic_snapshots, "unique_views")),
        "referrer_table": DashboardService.aggregate_referrers(traffic_referrers),
        "referrer_series": _json_script(
            _strip_thin_series(
                DashboardService.format_referrer_series(traffic_referrers)
            )
        ),
        "referrer_daily_series": _json_script(
            _strip_thin_series(
                DashboardService.format_referrer_daily_estimates(traffic_referrers)
            )
        ),
    }


class DashboardController(Controller):
    path = "/p"
    guards = [require_login]

    @get("/{owner:str}/{repo:str}", name="dashboard:project")
    async def project_dashboard(
        self,
        request: Request,
        user: User,
        db_session: AsyncSession,
        owner: str,
        repo: str,
    ) -> Template | Redirect:
        github_repo = f"{owner}/{repo}"
        result = await db_session.execute(
            select(Project).where(Project.github_repo == github_repo)
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise NotFoundException("Project not found")

        if project.user_id != user.id:
            raise NotFoundException("Project not found")

        dashboard = DashboardService(db_session)

        # Parse time range
        range_key = request.query_params.get("range", DEFAULT_RANGE)
        if range_key not in TIME_RANGES:
            range_key = DEFAULT_RANGE
        time_range = TIME_RANGES[range_key]
        since = datetime.now(timezone.utc).date() - timedelta(days=time_range["days"])
        weekly_weeks = time_range["weeks"]

        # Fetch data
        github_snapshots = await dashboard.get_github_snapshots(project.id, since=since)
        latest_gh = github_snapshots[-1] if github_snapshots else None
        week_ago_gh = await dashboard.get_github_snapshot_near_date(
            project.id, datetime.now(timezone.utc).date() - timedelta(days=7)
        )

        latest_release_tag = latest_gh.latest_release_tag if latest_gh else None
        latest_pkg = await dashboard.get_latest_package_snapshots(project.id)
        matrix = DashboardService.format_packaging_matrix(
            project.package_mappings, latest_pkg, latest_release_tag
        )

        mapping_ids = [m.id for m in project.package_mappings]
        snaps_by_mapping = await dashboard.get_package_snapshots_batch(
            mapping_ids, since=since
        )
        release_downloads = await dashboard.get_release_downloads(project.id)
        traffic_snapshots = await dashboard.get_traffic_snapshots(
            project.id, since=since
        )
        traffic_referrers = await dashboard.get_traffic_referrers(
            project.id, since=since
        )

        # Build context sections
        gh_ctx = _build_github_series(github_snapshots, weekly_weeks)
        pkg_ctx = _build_package_series(project, snaps_by_mapping, github_snapshots)
        release_ctx = _build_release_context(release_downloads)
        traffic_ctx = _build_traffic_context(traffic_snapshots, traffic_referrers)

        # Merge release download daily-delta into the package download series
        release_dl_entry = release_ctx.pop("release_download_entry", None)
        if release_dl_entry is not None:
            dl = json.loads(pkg_ctx["download_series"])
            dl.append(release_dl_entry)
            pkg_ctx["download_series"] = _json_script(_strip_thin_series(dl))

        next_scan_utc, next_scan_in = _compute_next_scan(project.id)

        return Template(
            template_name="projects/dashboard.html",
            context={
                "project": project,
                "latest_gh": latest_gh,
                "deltas": DashboardService.compute_github_deltas(
                    latest_gh, week_ago_gh
                ),
                "total_downloads": DashboardService.compute_total_downloads(matrix),
                "latest_release_tag": latest_release_tag,
                "latest_release_ago": _format_release_ago(latest_gh),
                "has_chart_data": len(github_snapshots) >= 1,
                "traction": DashboardService.compute_traction_metrics(
                    github_snapshots, latest_gh, matrix
                ),
                "last_scan_date": latest_gh.date if latest_gh else None,
                "next_scan_utc": next_scan_utc,
                "next_scan_in": next_scan_in,
                "matrix": matrix,
                "weekly_label": f"{weekly_weeks}w",
                "daily_label": time_range["label"],
                "user": user,
                **gh_ctx,
                **pkg_ctx,
                **release_ctx,
                **traffic_ctx,
            },
        )
