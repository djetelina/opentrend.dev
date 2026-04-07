import asyncio
import json
import logging
import re
import uuid
from datetime import date, datetime

import niquests
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opentrend import USER_AGENT
from opentrend.github_utils import GITHUB_API, github_headers
from opentrend.metrics import instrumented_client
from opentrend.collectors.base import ProjectCollector
from opentrend.models.project import Project
from opentrend.models.snapshot import GithubSnapshot, ReleaseDownloadSnapshot

logger = logging.getLogger(__name__)


class GithubCollector(ProjectCollector):
    def __init__(self, token: str) -> None:
        self._token = token

    def _headers(self) -> dict[str, str]:
        return github_headers(self._token)

    @staticmethod
    def parse_repo(data: dict) -> dict:
        return {
            "stars": data["stargazers_count"],
            "forks": data["forks_count"],
            "open_issues": data["open_issues_count"],
            "watchers": data["subscribers_count"],
            "license": data.get("license", {}).get("spdx_id")
            if data.get("license")
            else None,
        }

    @staticmethod
    def parse_releases(releases: list[dict]) -> dict:
        assets = []
        for r in releases:
            for a in r.get("assets", []):
                assets.append(
                    {
                        "release_tag": r["tag_name"],
                        "asset_name": a["name"],
                        "download_count": a["download_count"],
                    }
                )

        latest_date = None
        latest_tag = None
        if releases:
            latest_tag = releases[0].get("tag_name")
            published = releases[0].get("published_at")
            if published:
                latest_date = datetime.fromisoformat(published)

        return {
            "release_count": len(releases),
            "latest_release_date": latest_date,
            "latest_release_tag": latest_tag,
            "assets": assets,
        }

    async def _fetch_stats(
        self, client: niquests.AsyncSession, url: str
    ) -> dict | list | None:
        """Fetch a GitHub stats endpoint (3 attempts total, retrying on 202/computing)."""
        for _ in range(3):
            resp = await client.get(url, headers=self._headers())
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 202:
                await asyncio.sleep(2)
                continue
            logger.warning("GitHub stats %s returned %d", url, resp.status_code)
            return None
        logger.warning("GitHub stats %s still computing after 3 attempts", url)
        return None

    async def _fetch_all_pages(
        self,
        client: niquests.AsyncSession,
        url: str,
        params: dict | None = None,
        max_pages: int = 50,
    ) -> list[dict]:
        results = []
        params = params or {}
        params.setdefault("per_page", "100")
        page = 1
        while page <= max_pages:
            params["page"] = str(page)
            resp = await client.get(url, params=params, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            results.extend(data)
            if len(data) < 100:
                break
            page += 1
        if page > max_pages:
            logger.warning("Hit max_pages (%d) fetching %s", max_pages, url)
        return results

    async def collect(
        self, session: AsyncSession, project_id: uuid.UUID, snapshot_date: date
    ) -> None:
        result = await session.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one()
        repo = project.github_repo

        async with instrumented_client() as client:
            headers = self._headers()

            async def _search_count(query: str) -> int:
                r = await client.get(
                    f"{GITHUB_API}/search/issues", params={"q": query}, headers=headers
                )
                r.raise_for_status()
                return r.json()["total_count"]

            async def _commit_count() -> int:
                r = await client.get(
                    f"{GITHUB_API}/repos/{repo}/commits",
                    params={"per_page": "1"},
                    headers=headers,
                )
                r.raise_for_status()
                link = r.headers.get("Link", "")
                if 'rel="last"' in link:
                    match = re.search(r'page=(\d+)>; rel="last"', link)
                    if match:
                        return int(match.group(1))
                return 1 if r.json() else 0

            async def _community() -> int | None:
                r = await client.get(
                    f"{GITHUB_API}/repos/{repo}/community/profile", headers=headers
                )
                return (
                    r.json().get("health_percentage") if r.status_code == 200 else None
                )

            # Repo info must come first (need basic data), everything else in parallel
            resp = await client.get(f"{GITHUB_API}/repos/{repo}", headers=headers)
            resp.raise_for_status()
            repo_data = self.parse_repo(resp.json())

            results = await asyncio.gather(
                _search_count(f"repo:{repo} type:issue state:closed"),
                _search_count(f"repo:{repo} type:pr state:open"),
                _search_count(f"repo:{repo} type:pr state:closed"),
                self._fetch_all_pages(
                    client, f"{GITHUB_API}/repos/{repo}/contributors"
                ),
                _commit_count(),
                self._fetch_all_pages(client, f"{GITHUB_API}/repos/{repo}/releases"),
                self._fetch_stats(
                    client, f"{GITHUB_API}/repos/{repo}/stats/commit_activity"
                ),
                self._fetch_stats(
                    client, f"{GITHUB_API}/repos/{repo}/stats/code_frequency"
                ),
                self._fetch_stats(
                    client, f"{GITHUB_API}/repos/{repo}/stats/contributors"
                ),
                _community(),
                return_exceptions=True,
            )

            _labels = [
                "closed_issues",
                "open_prs",
                "closed_prs",
                "contributors",
                "commits_total",
                "releases",
                "commit_activity",
                "code_frequency",
                "contributors_stats",
                "community_health",
            ]
            resolved = []
            for label, result in zip(_labels, results):
                if isinstance(result, BaseException):
                    logger.warning("GitHub %s failed for %s: %s", label, repo, result)
                    resolved.append(None)
                else:
                    resolved.append(result)

            (
                closed_issues,
                open_prs,
                closed_prs,
                contributors,
                commits_total,
                releases,
                commit_activity,
                code_frequency,
                contributors_stats,
                community_health,
            ) = resolved
            release_data = self.parse_releases(releases or [])

        # Dependents (scraped from web UI — separate client, no auth headers)
        dependents_repos = None
        dependents_packages = None
        try:
            async with instrumented_client(
                timeout=15, headers={"User-Agent": USER_AGENT}
            ) as web_client:
                dep_resp = await web_client.get(
                    f"https://github.com/{repo}/network/dependents",
                    allow_redirects=True,
                )
                if dep_resp.status_code == 200:
                    repo_m = re.search(
                        r"<svg[^>]*>.*?</svg>\s*([\d,]+)\s*Repositories",
                        dep_resp.text,
                        re.DOTALL,
                    )
                    pkg_m = re.search(
                        r"<svg[^>]*>.*?</svg>\s*([\d,]+)\s*Packages",
                        dep_resp.text,
                        re.DOTALL,
                    )
                    if repo_m or pkg_m:
                        dependents_repos = (
                            int(repo_m.group(1).replace(",", "")) if repo_m else 0
                        )
                        dependents_packages = (
                            int(pkg_m.group(1).replace(",", "")) if pkg_m else 0
                        )
        except (
            niquests.exceptions.RequestException,
            ValueError,
            TypeError,
            AttributeError,
        ):
            logger.warning("Failed to scrape dependents for %s", repo, exc_info=True)

        # Serialize stats to JSON
        weekly_commits = (
            json.dumps(
                [{"week": w["week"], "total": w["total"]} for w in commit_activity]
            )
            if commit_activity
            else None
        )
        weekly_code_frequency = json.dumps(code_frequency) if code_frequency else None

        # Build owner vs community from /stats/contributors
        # (participation endpoint conflates bots with community; contributors lets us filter by login)
        # Owner = repo owner login, bots = *[bot], community = everyone else
        weekly_owner_commits = None
        weekly_all_commits = None
        if contributors_stats and isinstance(contributors_stats, list):
            owner_login = repo.split("/")[0]
            num_weeks = max(
                (len(c.get("weeks", [])) for c in contributors_stats), default=0
            )
            owner_weekly = [0] * num_weeks
            all_weekly = [0] * num_weeks
            for contributor in contributors_stats:
                login = contributor.get("author", {}).get("login", "")
                is_bot = login.endswith("[bot]")
                weeks = contributor.get("weeks", [])
                for i, w in enumerate(weeks):
                    commits_count = w.get("c", 0)
                    if not is_bot:
                        all_weekly[i] += commits_count
                    if login == owner_login:
                        owner_weekly[i] += commits_count
            weekly_owner_commits = json.dumps(owner_weekly)
            weekly_all_commits = json.dumps(all_weekly)

        # Build snapshot fields once, use for both insert and update
        # Core repo fields always present (from /repos endpoint which must succeed)
        fields = {
            "stars": repo_data["stars"],
            "forks": repo_data["forks"],
            "open_issues": repo_data["open_issues"],
            "watchers": repo_data["watchers"],
            "license": repo_data["license"],
        }
        # Optional fields: only update when not None (preserve previous values
        # on transient API failures instead of overwriting with 0)
        optional = {
            "closed_issues": closed_issues,
            "open_prs": open_prs,
            "closed_prs": closed_prs,
            "contributors": len(contributors) if contributors is not None else None,
            "commits_total": commits_total,
            "latest_release_date": release_data["latest_release_date"],
            "latest_release_tag": release_data["latest_release_tag"],
            "release_count": release_data["release_count"],
            "weekly_commits": weekly_commits,
            "weekly_code_frequency": weekly_code_frequency,
            "weekly_owner_commits": weekly_owner_commits,
            "weekly_all_commits": weekly_all_commits,
            "community_health": community_health,
        }
        if dependents_repos is not None:
            optional["dependents_repos"] = dependents_repos
            optional["dependents_packages"] = dependents_packages

        github_result = await session.execute(
            select(GithubSnapshot).where(
                GithubSnapshot.project_id == project_id,
                GithubSnapshot.date == snapshot_date,
            )
        )
        snapshot = github_result.scalar_one_or_none()
        if snapshot:
            for k, v in fields.items():
                setattr(snapshot, k, v)
            for k, v in optional.items():
                if v is not None:
                    setattr(snapshot, k, v)
        else:
            all_fields = {
                **fields,
                **{k: v for k, v in optional.items() if v is not None},
            }
            session.add(
                GithubSnapshot(
                    project_id=project_id,
                    date=snapshot_date,
                    **all_fields,
                )
            )

        # Batch-fetch existing release download snapshots for today
        if release_data["assets"]:
            rds_result = await session.execute(
                select(ReleaseDownloadSnapshot).where(
                    ReleaseDownloadSnapshot.project_id == project_id,
                    ReleaseDownloadSnapshot.date == snapshot_date,
                )
            )
            existing_rds = {
                (r.release_tag, r.asset_name): r for r in rds_result.scalars().all()
            }
        else:
            existing_rds = {}

        for asset in release_data["assets"]:
            key = (asset["release_tag"], asset["asset_name"])
            rds = existing_rds.get(key)
            if rds:
                rds.download_count = asset["download_count"]
            else:
                session.add(
                    ReleaseDownloadSnapshot(
                        project_id=project_id,
                        date=snapshot_date,
                        release_tag=asset["release_tag"],
                        asset_name=asset["asset_name"],
                        download_count=asset["download_count"],
                    )
                )

        await session.commit()
