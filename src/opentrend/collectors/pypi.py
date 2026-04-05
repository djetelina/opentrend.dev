from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from opentrend import USER_AGENT
from opentrend.metrics import instrumented_client
from opentrend.collectors.base import PackageCollector

PYPI_API = "https://pypi.org/pypi"
PYPISTATS_API = "https://pypistats.org/api"


class PyPICollector(PackageCollector):
    @staticmethod
    def parse_package_info(data: dict) -> dict:
        return {
            "latest_version": data["info"]["version"],
            "version_count": len(data.get("releases", {})),
        }

    @staticmethod
    def parse_download_stats(data: dict) -> dict:
        d = data["data"]
        return {
            "downloads_daily": d.get("last_day", 0),
            "downloads_weekly": d.get("last_week", 0),
            "downloads_monthly": d.get("last_month", 0),
        }

    async def collect(
        self, session: AsyncSession, mapping_id: int, snapshot_date: date
    ) -> None:
        mapping = await self.get_mapping(session, mapping_id)
        pkg_name = mapping.package_name

        async with instrumented_client(headers={"User-Agent": USER_AGENT}) as client:
            resp = await client.get(f"{PYPI_API}/{pkg_name}/json")
            resp.raise_for_status()
            info = self.parse_package_info(resp.json())

            resp = await client.get(f"{PYPISTATS_API}/packages/{pkg_name}/recent")
            resp.raise_for_status()
            stats = self.parse_download_stats(resp.json())

        await self.upsert_package_snapshot(
            session,
            mapping_id,
            snapshot_date,
            downloads_daily=stats["downloads_daily"],
            downloads_weekly=stats["downloads_weekly"],
            downloads_monthly=stats["downloads_monthly"],
            latest_version=info["latest_version"],
            version_count=info["version_count"],
        )
        await session.commit()
