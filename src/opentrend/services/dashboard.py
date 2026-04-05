import json
import math
import re
import uuid
from collections import defaultdict

from packaging.version import InvalidVersion, Version
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from opentrend.models.project import PackageMapping
from opentrend.models.snapshot import (
    GithubSnapshot,
    PackageSnapshot,
    ReleaseDownloadSnapshot,
    TrafficReferrerSnapshot,
    TrafficSnapshot,
)
from opentrend.types import (
    GithubDeltas,
    NamedSeries,
    PackagingMatrixRow,
    ReferrerAggregate,
    ReleaseAsset,
    ReleaseSummary,
    TimeSeriesPoint,
)


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def format_time_series(snapshots: list, field: str) -> list[TimeSeriesPoint]:
        return [
            {"date": s.date.isoformat(), "value": getattr(s, field)} for s in snapshots
        ]

    @staticmethod
    def format_packaging_matrix(
        packages: list[PackageMapping],
        latest_snapshots: dict[int, PackageSnapshot],
        latest_release_tag: str | None = None,
    ) -> list[PackagingMatrixRow]:
        matrix: list[PackagingMatrixRow] = []
        for pkg in packages:
            snap = latest_snapshots.get(pkg.id)
            version = snap.latest_version if snap else None

            # Determine freshness relative to latest GitHub release
            freshness = "unknown"
            if version and latest_release_tag:
                try:
                    # Normalize underscores to dots (e.g. curl-8_19_0 → curl-8.19.0)
                    ver_normalized = version.replace("_", ".")
                    rel_normalized = latest_release_tag.replace("_", ".")
                    ver_clean = re.search(r"(\d+[\d.]*\d+)", ver_normalized)
                    rel_clean = re.search(r"(\d+[\d.]*\d+)", rel_normalized)
                    if ver_clean and rel_clean:
                        v = Version(ver_clean.group(1))
                        r = Version(rel_clean.group(1))
                        freshness = "current" if v >= r else "outdated"
                except InvalidVersion:
                    pass

            matrix.append(
                {
                    "source": pkg.source,
                    "package_name": pkg.package_name,
                    "version": version,
                    "freshness": freshness,
                    "votes": snap.votes if snap else None,
                    "popularity": snap.popularity if snap else None,
                    "downloads_daily": snap.downloads_daily if snap else None,
                    "downloads_weekly": snap.downloads_weekly if snap else None,
                    "downloads_monthly": snap.downloads_monthly if snap else None,
                    "downloads_total": snap.downloads_total if snap else None,
                    "dependents_count": snap.dependents_count if snap else None,
                }
            )
        return matrix

    @staticmethod
    def compute_github_deltas(
        latest: GithubSnapshot | None,
        week_ago: GithubSnapshot | None,
    ) -> GithubDeltas:
        if not latest or not week_ago:
            return GithubDeltas()
        return GithubDeltas(
            stars_delta=(latest.stars or 0) - (week_ago.stars or 0),
            forks_delta=(latest.forks or 0) - (week_ago.forks or 0),
            issues_delta=(latest.open_issues or 0) - (week_ago.open_issues or 0),
        )

    @staticmethod
    def compute_reach(
        gh: GithubSnapshot | None,
        matrix: list[PackagingMatrixRow],
        total_downloads: int,
        traffic_views: int = 0,
        traffic_clones: int = 0,
    ) -> int:
        """Composite reach score: weighted sum of sqrt(stars)*30, sqrt(forks)*20, and log1p-scaled contributors, watchers, sources, downloads, dependents, and traffic."""
        if not gh:
            return 0
        source_count = sum(1 for r in matrix if r.get("version"))
        # GitHub dependents (authoritative), fall back to registry dependents
        gh_deps = (gh.dependents_repos or 0) + (gh.dependents_packages or 0)
        total_dependents = (
            gh_deps
            if gh_deps > 0
            else sum(r.get("dependents_count") or 0 for r in matrix)
        )
        return round(
            math.sqrt(gh.stars) * 30
            + math.sqrt(gh.forks) * 20
            + math.log1p(gh.contributors or 0) * 40
            + math.log1p(gh.watchers or 0) * 20
            + math.log1p(source_count) * 50
            + math.log1p(total_downloads) * 20
            + math.log1p(total_dependents) * 40
            + math.log1p(traffic_views) * 15
            + math.log1p(traffic_clones) * 15
        )

    @staticmethod
    def compute_total_downloads(matrix: list[PackagingMatrixRow]) -> int:
        return sum(
            (row["downloads_monthly"] or 0)
            if row.get("downloads_monthly")
            else (
                (row["downloads_daily"] or 0) * 30 if row.get("downloads_daily") else 0
            )
            for row in matrix
        )

    @staticmethod
    def summarize_releases(
        release_downloads: list[ReleaseDownloadSnapshot],
    ) -> list[ReleaseSummary]:
        """Group release downloads by release_tag using the latest snapshot per asset.

        GitHub reports cumulative download counts, so we only want the most
        recent snapshot for each (release_tag, asset_name) pair — older
        snapshots are superseded by newer ones.
        """
        # Keep only the latest snapshot per (release_tag, asset_name)
        latest_by_key: dict[tuple[str, str], ReleaseDownloadSnapshot] = {}
        for dl in release_downloads:
            key = (dl.release_tag, dl.asset_name)
            if key not in latest_by_key or dl.date > latest_by_key[key].date:
                latest_by_key[key] = dl

        by_tag: dict[str, ReleaseSummary] = {}
        for dl in latest_by_key.values():
            if dl.release_tag not in by_tag:
                by_tag[dl.release_tag] = ReleaseSummary(
                    release_tag=dl.release_tag,
                    date=dl.date,
                    total_downloads=0,
                    assets=[],
                )
            entry = by_tag[dl.release_tag]
            entry["total_downloads"] += dl.download_count
            entry["assets"].append(
                ReleaseAsset(
                    asset_name=dl.asset_name,
                    download_count=dl.download_count,
                )
            )
        return list(by_tag.values())

    @staticmethod
    def compute_traction_metrics(
        github_snapshots: list[GithubSnapshot],
        latest_gh: GithubSnapshot | None,
        matrix: list[PackagingMatrixRow],
    ) -> dict:
        """Compute derived traction indicators from existing data."""
        metrics: dict = {}
        if not latest_gh or len(github_snapshots) < 2:
            return metrics

        # Growth rates (7-day and 30-day)
        today_snap = github_snapshots[-1]
        week_ago = next(
            (
                s
                for s in reversed(github_snapshots)
                if s.date <= today_snap.date - timedelta(days=7)
            ),
            None,
        )
        month_ago = next(
            (
                s
                for s in reversed(github_snapshots)
                if s.date <= today_snap.date - timedelta(days=30)
            ),
            None,
        )

        if week_ago and week_ago.stars > 0:
            metrics["stars_growth_weekly"] = round(
                (today_snap.stars - week_ago.stars) / week_ago.stars * 100, 2
            )
        if month_ago and month_ago.stars > 0:
            metrics["stars_growth_monthly"] = round(
                (today_snap.stars - month_ago.stars) / month_ago.stars * 100, 2
            )
        if week_ago and week_ago.forks > 0:
            metrics["forks_growth_weekly"] = round(
                (today_snap.forks - week_ago.forks) / week_ago.forks * 100, 2
            )

        # Fork-to-star ratio
        if latest_gh.stars > 0:
            metrics["fork_star_ratio"] = round(
                latest_gh.forks / latest_gh.stars * 100, 1
            )

        # Issue close rate (closed per period vs opened per period)
        if (
            week_ago
            and today_snap.closed_issues is not None
            and week_ago.closed_issues is not None
        ):
            new_closed = today_snap.closed_issues - week_ago.closed_issues
            new_opened = (
                (today_snap.open_issues or 0) - (today_snap.open_prs or 0)
            ) - ((week_ago.open_issues or 0) - (week_ago.open_prs or 0))
            if new_opened > 0:
                metrics["issue_close_rate"] = round(new_closed / new_opened, 1)

        # PR close rate (closed ≈ merged; GitHub API does not distinguish)
        if (
            week_ago
            and today_snap.closed_prs is not None
            and week_ago.closed_prs is not None
        ):
            new_merged = today_snap.closed_prs - week_ago.closed_prs
            new_prs = (today_snap.open_prs or 0) - (week_ago.open_prs or 0) + new_merged
            if new_prs > 0:
                metrics["pr_merge_rate"] = round(new_merged / new_prs * 100, 1)

        # Community participation (from latest stats)
        if latest_gh.weekly_all_commits and latest_gh.weekly_owner_commits:
            all_commits = json.loads(latest_gh.weekly_all_commits)
            owner_commits = json.loads(latest_gh.weekly_owner_commits)
            total_all = sum(all_commits[-12:])  # last 12 weeks
            total_owner = sum(owner_commits[-12:])
            if total_all > 0:
                metrics["community_pct"] = round(
                    (total_all - total_owner) / total_all * 100, 1
                )

        # Community health score
        if latest_gh.community_health is not None:
            metrics["community_health"] = latest_gh.community_health

        # Package adoption breadth
        total_sources = len(matrix)
        sources_with_version = sum(1 for r in matrix if r.get("version"))
        if total_sources > 0:
            metrics["package_breadth"] = f"{sources_with_version}/{total_sources}"
            metrics["package_breadth_pct"] = round(
                sources_with_version / total_sources * 100
            )

        # Version freshness rate
        current_count = sum(1 for r in matrix if r.get("freshness") == "current")
        versioned = sum(1 for r in matrix if r.get("version"))
        if versioned > 0:
            metrics["freshness_rate"] = round(current_count / versioned * 100)

        # Total dependents across all package sources
        total_deps = sum(r.get("dependents_count") or 0 for r in matrix)
        if total_deps > 0:
            metrics["total_dependents"] = total_deps

        return metrics

    @staticmethod
    def parse_weekly_commits(
        snapshot: GithubSnapshot | None, weeks: int = 52
    ) -> list[TimeSeriesPoint]:
        """Parse weekly_commits JSON into chart-friendly format."""
        if not snapshot or not snapshot.weekly_commits:
            return []
        data = json.loads(snapshot.weekly_commits)
        data = data[-weeks:]
        return [
            {"date": date.fromtimestamp(w["week"]).isoformat(), "value": w["total"]}
            for w in data
        ]

    @staticmethod
    def parse_code_frequency(
        snapshot: GithubSnapshot | None, weeks: int = 52
    ) -> tuple[list[TimeSeriesPoint], list[TimeSeriesPoint]]:
        """Parse code_frequency JSON into additions and deletions series.

        Only returns the last ``weeks`` entries to align with other
        GitHub stats charts (weekly commits, participation).
        """
        if not snapshot or not snapshot.weekly_code_frequency:
            return [], []
        data = json.loads(snapshot.weekly_code_frequency)
        # Trim to last N weeks to match other chart time ranges
        data = data[-weeks:]
        additions = []
        deletions = []
        for row in data:
            d = date.fromtimestamp(row[0]).isoformat()
            additions.append({"date": d, "value": row[1]})
            deletions.append({"date": d, "value": abs(row[2])})
        return additions, deletions

    @staticmethod
    def _compute_52_week_dates(snapshot: GithubSnapshot | None) -> list[str]:
        """Compute real dates for 52-week GitHub stats data."""
        # Try to use commit_activity timestamps first (most accurate)
        if snapshot and snapshot.weekly_commits:
            commits = json.loads(snapshot.weekly_commits)
            return [date.fromtimestamp(w["week"]).isoformat() for w in commits]
        # Fall back to computing from today - 52 weeks
        today = datetime.now(timezone.utc).date()
        # GitHub weeks start on Sunday; week 0 is ~52 weeks ago
        start = today - timedelta(weeks=52)
        return [(start + timedelta(weeks=i)).isoformat() for i in range(52)]

    @staticmethod
    def parse_participation(
        snapshot: GithubSnapshot | None, weeks: int = 52
    ) -> tuple[list[TimeSeriesPoint], list[TimeSeriesPoint]]:
        """Parse participation into owner and community series."""
        if (
            not snapshot
            or not snapshot.weekly_all_commits
            or not snapshot.weekly_owner_commits
        ):
            return [], []
        all_data = json.loads(snapshot.weekly_all_commits)
        owner_data = json.loads(snapshot.weekly_owner_commits)
        timestamps = DashboardService._compute_52_week_dates(snapshot)

        # Trim all three lists to the last N weeks
        all_data = all_data[-weeks:]
        owner_data = owner_data[-weeks:]
        timestamps = timestamps[-weeks:]

        owner_series = []
        community_series = []
        for total, owner, d in zip(all_data, owner_data, timestamps):
            owner_series.append({"date": d, "value": owner})
            community_series.append({"date": d, "value": max(0, total - owner)})
        return owner_series, community_series

    async def get_github_snapshots(
        self, project_id: uuid.UUID, since: date | None = None
    ) -> list[GithubSnapshot]:
        stmt = (
            select(GithubSnapshot)
            .where(GithubSnapshot.project_id == project_id)
            .order_by(GithubSnapshot.date)
        )
        if since:
            stmt = stmt.where(GithubSnapshot.date >= since)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_github_snapshots_batch(
        self, project_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[GithubSnapshot]]:
        """Fetch all GitHub snapshots for multiple projects in one query."""
        stmt = (
            select(GithubSnapshot)
            .where(GithubSnapshot.project_id.in_(project_ids))
            .order_by(GithubSnapshot.project_id, GithubSnapshot.date)
        )
        result = await self._session.execute(stmt)
        by_project: dict[uuid.UUID, list[GithubSnapshot]] = {
            pid: [] for pid in project_ids
        }
        for snap in result.scalars().all():
            by_project[snap.project_id].append(snap)
        return by_project

    async def get_latest_package_snapshots_batch(
        self, project_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, dict[int, PackageSnapshot]]:
        """Fetch latest package snapshot per mapping for multiple projects in one query."""
        mapping_stmt = select(PackageMapping.id, PackageMapping.project_id).where(
            PackageMapping.project_id.in_(project_ids)
        )
        mapping_rows = await self._session.execute(mapping_stmt)
        mapping_to_project = {r.id: r.project_id for r in mapping_rows.all()}
        if not mapping_to_project:
            return {pid: {} for pid in project_ids}

        ranked = (
            select(
                PackageSnapshot,
                func.row_number()
                .over(
                    partition_by=PackageSnapshot.package_mapping_id,
                    order_by=desc(PackageSnapshot.date),
                )
                .label("rn"),
            )
            .where(PackageSnapshot.package_mapping_id.in_(mapping_to_project.keys()))
            .subquery()
        )
        stmt = select(PackageSnapshot).join(
            ranked,
            (PackageSnapshot.id == ranked.c.id) & (ranked.c.rn == 1),
        )
        result = await self._session.execute(stmt)
        by_project: dict[uuid.UUID, dict[int, PackageSnapshot]] = {
            pid: {} for pid in project_ids
        }
        for snap in result.scalars().all():
            pid = mapping_to_project[snap.package_mapping_id]
            by_project[pid][snap.package_mapping_id] = snap
        return by_project

    async def get_latest_github_snapshot(
        self, project_id: uuid.UUID
    ) -> GithubSnapshot | None:
        result = await self._session.execute(
            select(GithubSnapshot)
            .where(GithubSnapshot.project_id == project_id)
            .order_by(desc(GithubSnapshot.date))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_github_snapshot_near_date(
        self, project_id: uuid.UUID, target_date: date
    ) -> GithubSnapshot | None:
        """Get the snapshot closest to a target date (looking back)."""
        result = await self._session.execute(
            select(GithubSnapshot)
            .where(
                GithubSnapshot.project_id == project_id,
                GithubSnapshot.date <= target_date,
            )
            .order_by(desc(GithubSnapshot.date))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_package_snapshots(
        self, mapping_id: int, since: date | None = None
    ) -> list[PackageSnapshot]:
        stmt = (
            select(PackageSnapshot)
            .where(PackageSnapshot.package_mapping_id == mapping_id)
            .order_by(PackageSnapshot.date)
        )
        if since:
            stmt = stmt.where(PackageSnapshot.date >= since)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_package_snapshots_batch(
        self, mapping_ids: list[int], since: date | None = None
    ) -> dict[int, list[PackageSnapshot]]:
        """Fetch package snapshots for multiple mappings in one query."""
        stmt = (
            select(PackageSnapshot)
            .where(PackageSnapshot.package_mapping_id.in_(mapping_ids))
            .order_by(PackageSnapshot.package_mapping_id, PackageSnapshot.date)
        )
        if since:
            stmt = stmt.where(PackageSnapshot.date >= since)
        result = await self._session.execute(stmt)
        by_mapping: dict[int, list[PackageSnapshot]] = {mid: [] for mid in mapping_ids}
        for snap in result.scalars().all():
            by_mapping[snap.package_mapping_id].append(snap)
        return by_mapping

    async def get_latest_package_snapshots(
        self, project_id: uuid.UUID
    ) -> dict[int, PackageSnapshot]:
        """Get the most recent snapshot for each package mapping of a project."""
        mapping_ids = select(PackageMapping.id).where(
            PackageMapping.project_id == project_id
        )
        ranked = (
            select(
                PackageSnapshot,
                func.row_number()
                .over(
                    partition_by=PackageSnapshot.package_mapping_id,
                    order_by=desc(PackageSnapshot.date),
                )
                .label("rn"),
            )
            .where(PackageSnapshot.package_mapping_id.in_(mapping_ids))
            .subquery()
        )
        stmt = select(PackageSnapshot).join(
            ranked,
            (PackageSnapshot.id == ranked.c.id) & (ranked.c.rn == 1),
        )
        result = await self._session.execute(stmt)
        return {s.package_mapping_id: s for s in result.scalars().all()}

    async def get_release_downloads(
        self, project_id: uuid.UUID
    ) -> list[ReleaseDownloadSnapshot]:
        result = await self._session.execute(
            select(ReleaseDownloadSnapshot).where(
                ReleaseDownloadSnapshot.project_id == project_id
            )
        )
        return list(result.scalars().all())

    async def get_traffic_snapshots(
        self, project_id: uuid.UUID, since: date | None = None
    ) -> list[TrafficSnapshot]:
        stmt = (
            select(TrafficSnapshot)
            .where(TrafficSnapshot.project_id == project_id)
            .order_by(TrafficSnapshot.date)
        )
        if since:
            stmt = stmt.where(TrafficSnapshot.date >= since)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_traffic_referrers(
        self, project_id: uuid.UUID, since: date | None = None
    ) -> list[TrafficReferrerSnapshot]:
        stmt = (
            select(TrafficReferrerSnapshot)
            .where(TrafficReferrerSnapshot.project_id == project_id)
            .order_by(desc(TrafficReferrerSnapshot.date))
        )
        if since:
            stmt = stmt.where(TrafficReferrerSnapshot.date >= since)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def aggregate_referrers(
        referrers: list[TrafficReferrerSnapshot],
    ) -> list[ReferrerAggregate]:
        totals: dict[str, ReferrerAggregate] = {}
        for r in referrers:
            if r.referrer not in totals:
                totals[r.referrer] = ReferrerAggregate(
                    referrer=r.referrer, views=0, unique_visitors=0
                )
            totals[r.referrer]["views"] += r.views
            totals[r.referrer]["unique_visitors"] += r.unique_visitors
        return sorted(totals.values(), key=lambda x: x["views"], reverse=True)

    @staticmethod
    def format_referrer_series(
        referrers: list[TrafficReferrerSnapshot],
    ) -> list[NamedSeries]:
        """Raw 14-day rolling values per referrer per day (what GitHub reported)."""
        by_referrer: dict[str, dict[str, int]] = defaultdict(dict)
        for r in referrers:
            by_referrer[r.referrer][r.date.isoformat()] = r.views
        all_dates = sorted({r.date.isoformat() for r in referrers})
        series = []
        for referrer, date_map in by_referrer.items():
            series.append(
                {
                    "name": referrer,
                    "data": [
                        {"date": d, "value": date_map.get(d, 0)} for d in all_dates
                    ],
                }
            )
        series.sort(key=lambda s: sum(p["value"] for p in s["data"]), reverse=True)
        return series

    @staticmethod
    def format_referrer_daily_estimates(
        referrers: list[TrafficReferrerSnapshot],
    ) -> list[NamedSeries]:
        """Estimate daily referrer views by diffing consecutive 14-day snapshots.

        GitHub's referrer endpoint returns 14-day rolling totals (not daily values),
        so diffing consecutive days' snapshots approximates the daily referral count.
        """
        by_referrer: dict[str, dict[str, int]] = defaultdict(dict)
        for r in referrers:
            by_referrer[r.referrer][r.date.isoformat()] = r.views

        all_dates = sorted({r.date.isoformat() for r in referrers})
        if len(all_dates) < 2:
            return []

        series = []
        for referrer, date_map in by_referrer.items():
            data = []
            for i in range(1, len(all_dates)):
                prev = date_map.get(all_dates[i - 1], 0)
                curr = date_map.get(all_dates[i], 0)
                delta = max(0, curr - prev)
                data.append({"date": all_dates[i], "value": delta})
            series.append({"name": referrer, "data": data})
        series.sort(key=lambda s: sum(p["value"] for p in s["data"]), reverse=True)
        return series
