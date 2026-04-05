import logging
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

import niquests

from opentrend import USER_AGENT
from opentrend.metrics import instrumented_client
from opentrend.collectors.base import PackageCollector

logger = logging.getLogger(__name__)

RUBYGEMS_API = "https://rubygems.org/api/v1"


class RubyGemsCollector(PackageCollector):
    @staticmethod
    def parse_gem(data: dict) -> dict:
        return {
            "latest_version": data["version"],
            "downloads_total": data["downloads"],
            "downloads_version": data.get("version_downloads", 0),
        }

    async def collect(
        self, session: AsyncSession, mapping_id: int, snapshot_date: date
    ) -> None:
        mapping = await self.get_mapping(session, mapping_id)

        async with instrumented_client(headers={"User-Agent": USER_AGENT}) as client:
            resp = await client.get(f"{RUBYGEMS_API}/gems/{mapping.package_name}.json")
            resp.raise_for_status()
            info = self.parse_gem(resp.json())

            resp = await client.get(
                f"{RUBYGEMS_API}/versions/{mapping.package_name}.json"
            )
            resp.raise_for_status()
            version_count = len(resp.json())

            # Reverse dependencies count
            dependents_count = None
            try:
                deps_resp = await client.get(
                    f"{RUBYGEMS_API}/gems/{mapping.package_name}/reverse_dependencies.json",
                )
                if deps_resp.status_code == 200:
                    dependents_count = len(deps_resp.json())
            except (
                niquests.exceptions.RequestException,
                KeyError,
                ValueError,
                TypeError,
            ):
                logger.warning(
                    "Failed to fetch rubygems dependents for %s",
                    mapping.package_name,
                    exc_info=True,
                )

        await self.upsert_package_snapshot(
            session,
            mapping_id,
            snapshot_date,
            downloads_monthly=info["downloads_version"],
            latest_version=info["latest_version"],
            version_count=version_count,
            dependents_count=dependents_count,
        )
        await session.commit()
