import asyncio
import logging
import uuid
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opentrend.github_utils import GITHUB_API, github_headers
from opentrend.metrics import instrumented_client
from opentrend.collectors.base import ProjectCollector
from opentrend.models.project import Project
from opentrend.models.snapshot import TrafficReferrerSnapshot, TrafficSnapshot

logger = logging.getLogger(__name__)


class TrafficCollector(ProjectCollector):
    def __init__(self, token: str) -> None:
        self._token = token

    def _headers(self) -> dict[str, str]:
        return github_headers(self._token)

    async def collect(
        self, session: AsyncSession, project_id: uuid.UUID, snapshot_date: date
    ) -> None:
        result = await session.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one()
        repo = project.github_repo

        async with instrumented_client() as client:
            headers = self._headers()

            # Check traffic access with clones; 403/404 means no push access, skip remaining calls
            clones_resp = await client.get(
                f"{GITHUB_API}/repos/{repo}/traffic/clones",
                params={"per": "day"},
                headers=headers,
            )
            if clones_resp.status_code in (403, 404):
                logger.info("No traffic access for %s, skipping", repo)
                return
            clones_resp.raise_for_status()
            clones_data = clones_resp.json()

            # Views + Referrers in parallel
            views_result, referrers_result = await asyncio.gather(
                client.get(
                    f"{GITHUB_API}/repos/{repo}/traffic/views",
                    params={"per": "day"},
                    headers=headers,
                ),
                client.get(
                    f"{GITHUB_API}/repos/{repo}/traffic/popular/referrers",
                    headers=headers,
                ),
                return_exceptions=True,
            )
            views_data = {}
            if isinstance(views_result, BaseException):
                logger.warning("Traffic views failed for %s: %s", repo, views_result)
            elif views_result.status_code != 200:
                logger.warning(
                    "Traffic views returned %d for %s",
                    views_result.status_code,
                    repo,
                )
            else:
                views_data = views_result.json()
            referrers_data = []
            if isinstance(referrers_result, BaseException):
                logger.warning(
                    "Traffic referrers failed for %s: %s", repo, referrers_result
                )
            elif referrers_result.status_code != 200:
                logger.warning(
                    "Traffic referrers returned %d for %s",
                    referrers_result.status_code,
                    repo,
                )
            else:
                referrers_data = referrers_result.json()

        # Build daily lookup from clones and views
        def _parse_date(timestamp: str) -> date:
            return datetime.fromisoformat(timestamp).date()

        clones_by_date = {
            _parse_date(e["timestamp"]): (e["count"], e["uniques"])
            for e in clones_data.get("clones", [])
        }
        views_by_date = {
            _parse_date(e["timestamp"]): (e["count"], e["uniques"])
            for e in views_data.get("views", [])
        }

        # Batch-fetch existing traffic snapshots for this project in the date range
        all_dates = clones_by_date.keys() | views_by_date.keys()
        if all_dates:
            existing_result = await session.execute(
                select(TrafficSnapshot).where(
                    TrafficSnapshot.project_id == project_id,
                    TrafficSnapshot.date.in_(all_dates),
                )
            )
            existing_by_date = {s.date: s for s in existing_result.scalars().all()}
        else:
            existing_by_date = {}

        for d in all_dates:
            clones, unique_clones = clones_by_date.get(d, (0, 0))
            views, unique_views = views_by_date.get(d, (0, 0))

            snapshot = existing_by_date.get(d)
            if snapshot:
                snapshot.clones = clones
                snapshot.unique_clones = unique_clones
                snapshot.views = views
                snapshot.unique_views = unique_views
            else:
                session.add(
                    TrafficSnapshot(
                        project_id=project_id,
                        date=d,
                        clones=clones,
                        unique_clones=unique_clones,
                        views=views,
                        unique_views=unique_views,
                    )
                )

        # Batch-fetch existing referrer snapshots for today
        if referrers_data:
            ref_result = await session.execute(
                select(TrafficReferrerSnapshot).where(
                    TrafficReferrerSnapshot.project_id == project_id,
                    TrafficReferrerSnapshot.date == snapshot_date,
                )
            )
            existing_refs = {s.referrer: s for s in ref_result.scalars().all()}
        else:
            existing_refs = {}

        for ref in referrers_data:
            snap = existing_refs.get(ref["referrer"])
            if snap:
                snap.views = ref["count"]
                snap.unique_visitors = ref["uniques"]
            else:
                session.add(
                    TrafficReferrerSnapshot(
                        project_id=project_id,
                        date=snapshot_date,
                        referrer=ref["referrer"],
                        views=ref["count"],
                        unique_visitors=ref["uniques"],
                    )
                )

        await session.commit()
