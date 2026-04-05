import logging
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from opentrend import USER_AGENT
from opentrend.metrics import instrumented_client
from opentrend.collectors.base import PackageCollector

logger = logging.getLogger(__name__)

MAVEN_SEARCH = "https://search.maven.org/solrsearch/select"


class MavenCollector(PackageCollector):
    @staticmethod
    def parse_search(data: dict) -> dict | None:
        docs = data.get("response", {}).get("docs", [])
        if not docs:
            return None
        doc = docs[0]
        return {
            "latest_version": doc.get("latestVersion"),
            "version_count": doc.get("versionCount"),
        }

    async def collect(
        self, session: AsyncSession, mapping_id: int, snapshot_date: date
    ) -> None:
        mapping = await self.get_mapping(session, mapping_id)

        if ":" not in mapping.package_name:
            logger.warning(
                "Maven package name must be groupId:artifactId, got: %s",
                mapping.package_name,
            )
            return

        group_id, artifact_id = mapping.package_name.split(":", 1)

        async with instrumented_client(headers={"User-Agent": USER_AGENT}) as client:
            resp = await client.get(
                MAVEN_SEARCH,
                params={
                    "q": f"g:{group_id} AND a:{artifact_id}",
                    "rows": 1,
                    "wt": "json",
                },
            )
            resp.raise_for_status()
            info = self.parse_search(resp.json())

        if info is None:
            logger.warning("Maven package not found: %s", mapping.package_name)
            return

        await self.upsert_package_snapshot(
            session,
            mapping_id,
            snapshot_date,
            latest_version=info["latest_version"],
            version_count=info["version_count"],
        )
        await session.commit()
