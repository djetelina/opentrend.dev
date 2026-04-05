import logging
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from opentrend import USER_AGENT
from opentrend.metrics import instrumented_client
from opentrend.collectors.base import PackageCollector

logger = logging.getLogger(__name__)

PACKAGIST_API = "https://packagist.org"


class PackagistCollector(PackageCollector):
    @staticmethod
    def parse_package(data: dict) -> dict:
        pkg = data["package"]
        versions = pkg.get("versions", {})
        # Filter out dev branches (keys starting with "dev-")
        stable_keys = [k for k in versions if not k.startswith("dev-")]
        latest = stable_keys[0] if stable_keys else None
        return {
            "latest_version": latest,
            "version_count": len(stable_keys),
            "downloads_daily": pkg.get("downloads", {}).get("daily"),
            "downloads_monthly": pkg.get("downloads", {}).get("monthly"),
            "downloads_total": pkg.get("downloads", {}).get("total"),
            "dependents_count": pkg.get("dependents"),
        }

    async def collect(
        self, session: AsyncSession, mapping_id: int, snapshot_date: date
    ) -> None:
        mapping = await self.get_mapping(session, mapping_id)

        async with instrumented_client(headers={"User-Agent": USER_AGENT}) as client:
            resp = await client.get(
                f"{PACKAGIST_API}/packages/{mapping.package_name}.json",
            )
            resp.raise_for_status()
            info = self.parse_package(resp.json())

        await self.upsert_package_snapshot(
            session,
            mapping_id,
            snapshot_date,
            latest_version=info["latest_version"],
            version_count=info["version_count"],
            downloads_daily=info["downloads_daily"],
            downloads_monthly=info["downloads_monthly"],
            downloads_total=info["downloads_total"],
            dependents_count=info["dependents_count"],
        )
        await session.commit()
