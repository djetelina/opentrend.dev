import logging
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

import niquests

from opentrend import USER_AGENT
from opentrend.metrics import instrumented_client
from opentrend.collectors.base import PackageCollector

logger = logging.getLogger(__name__)

CRATES_API = "https://crates.io/api/v1"


class CratesCollector(PackageCollector):
    @staticmethod
    def parse_crate(data: dict) -> dict:
        crate = data["crate"]
        return {
            "latest_version": crate["max_version"],
            "version_count": len(data.get("versions", [])),
            "downloads_total": crate["downloads"],
            "downloads_recent": crate.get("recent_downloads", 0),
        }

    async def collect(
        self, session: AsyncSession, mapping_id: int, snapshot_date: date
    ) -> None:
        mapping = await self.get_mapping(session, mapping_id)

        async with instrumented_client(headers={"User-Agent": USER_AGENT}) as client:
            resp = await client.get(
                f"{CRATES_API}/crates/{mapping.package_name}",
            )
            resp.raise_for_status()
            info = self.parse_crate(resp.json())

            # Reverse dependencies count
            dependents_count = None
            try:
                deps_resp = await client.get(
                    f"{CRATES_API}/crates/{mapping.package_name}/reverse_dependencies",
                    params={"per_page": "1"},
                )
                if deps_resp.status_code == 200:
                    dependents_count = deps_resp.json().get("meta", {}).get("total")
            except (
                niquests.exceptions.RequestException,
                KeyError,
                ValueError,
                TypeError,
            ):
                logger.warning(
                    "Failed to fetch crates.io dependents for %s",
                    mapping.package_name,
                    exc_info=True,
                )

        await self.upsert_package_snapshot(
            session,
            mapping_id,
            snapshot_date,
            downloads_monthly=info["downloads_recent"],
            downloads_total=info["downloads_total"],
            latest_version=info["latest_version"],
            version_count=info["version_count"],
            dependents_count=dependents_count,
        )
        await session.commit()
