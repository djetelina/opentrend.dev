import logging
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from opentrend import USER_AGENT
from opentrend.metrics import instrumented_client
from opentrend.collectors.base import PackageCollector

logger = logging.getLogger(__name__)

NUGET_SEARCH_API = "https://azuresearch-usnc.nuget.org/query"


class NuGetCollector(PackageCollector):
    @staticmethod
    def parse_search(data: dict, package_name: str) -> dict | None:
        """Find exact match (case-insensitive) in search results."""
        for entry in data.get("data", []):
            if entry.get("id", "").lower() == package_name.lower():
                return {
                    "latest_version": entry.get("version"),
                    "version_count": len(entry.get("versions", [])),
                    "downloads_total": entry.get("totalDownloads"),
                }
        return None

    async def collect(
        self, session: AsyncSession, mapping_id: int, snapshot_date: date
    ) -> None:
        mapping = await self.get_mapping(session, mapping_id)

        async with instrumented_client(headers={"User-Agent": USER_AGENT}) as client:
            resp = await client.get(
                NUGET_SEARCH_API,
                params={"q": mapping.package_name, "take": 5},
            )
            resp.raise_for_status()
            info = self.parse_search(resp.json(), mapping.package_name)

        if info is None:
            logger.warning("NuGet package not found: %s", mapping.package_name)
            return

        await self.upsert_package_snapshot(
            session,
            mapping_id,
            snapshot_date,
            latest_version=info["latest_version"],
            version_count=info["version_count"],
            downloads_total=info["downloads_total"],
        )
        await session.commit()
