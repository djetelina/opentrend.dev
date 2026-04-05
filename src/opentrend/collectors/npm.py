import asyncio
import logging
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

import niquests

from opentrend import USER_AGENT
from opentrend.metrics import instrumented_client
from opentrend.collectors.base import PackageCollector

logger = logging.getLogger(__name__)

NPM_REGISTRY = "https://registry.npmjs.org"
NPM_API = "https://api.npmjs.org"


class NpmCollector(PackageCollector):
    @staticmethod
    def parse_registry(data: dict) -> dict:
        return {
            "latest_version": data["dist-tags"]["latest"],
            "version_count": len(data.get("versions", {})),
        }

    async def collect(
        self, session: AsyncSession, mapping_id: int, snapshot_date: date
    ) -> None:
        mapping = await self.get_mapping(session, mapping_id)
        pkg = mapping.package_name

        async with instrumented_client(headers={"User-Agent": USER_AGENT}) as client:
            resp = await client.get(f"{NPM_REGISTRY}/{pkg}")
            resp.raise_for_status()
            info = self.parse_registry(resp.json())

            # Downloads — daily, weekly, monthly (independent, fetch in parallel)
            daily_resp, weekly_resp, monthly_resp = await asyncio.gather(
                client.get(f"{NPM_API}/downloads/point/last-day/{pkg}"),
                client.get(f"{NPM_API}/downloads/point/last-week/{pkg}"),
                client.get(f"{NPM_API}/downloads/point/last-month/{pkg}"),
            )
            daily_resp.raise_for_status()
            weekly_resp.raise_for_status()
            monthly_resp.raise_for_status()
            daily = daily_resp.json()["downloads"]
            weekly = weekly_resp.json()["downloads"]
            monthly = monthly_resp.json()["downloads"]

            # Dependents count via npm search
            dependents_count = None
            try:
                resp = await client.get(
                    f"{NPM_REGISTRY}/-/v1/search",
                    params={"text": pkg, "size": 1},
                )
                if resp.status_code == 200:
                    objects = resp.json().get("objects", [])
                    for obj in objects:
                        if obj.get("package", {}).get("name") == pkg:
                            dep_val = obj.get("dependents")
                            if dep_val is not None:
                                dependents_count = int(dep_val)
                            break
            except (
                niquests.exceptions.RequestException,
                KeyError,
                ValueError,
                TypeError,
            ):
                logger.warning(
                    "Failed to fetch npm dependents for %s", pkg, exc_info=True
                )

        await self.upsert_package_snapshot(
            session,
            mapping_id,
            snapshot_date,
            downloads_daily=daily,
            downloads_weekly=weekly,
            downloads_monthly=monthly,
            latest_version=info["latest_version"],
            version_count=info["version_count"],
            dependents_count=dependents_count,
        )
        await session.commit()
