import asyncio
import logging
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from opentrend import USER_AGENT
from opentrend.metrics import instrumented_client
from opentrend.collectors.base import PackageCollector

logger = logging.getLogger(__name__)

GO_PROXY = "https://proxy.golang.org"


class GoCollector(PackageCollector):
    @staticmethod
    def parse_latest(data: dict) -> str:
        return data["Version"]

    @staticmethod
    def parse_version_list(text: str) -> int:
        versions = [line for line in text.strip().splitlines() if line.strip()]
        return len(versions)

    async def collect(
        self, session: AsyncSession, mapping_id: int, snapshot_date: date
    ) -> None:
        mapping = await self.get_mapping(session, mapping_id)
        module = mapping.package_name

        async with instrumented_client(headers={"User-Agent": USER_AGENT}) as client:
            latest_resp, list_resp = await asyncio.gather(
                client.get(f"{GO_PROXY}/{module}/@latest"),
                client.get(f"{GO_PROXY}/{module}/@v/list"),
            )
            latest_resp.raise_for_status()
            latest_version = self.parse_latest(latest_resp.json())

            version_count = None
            if list_resp.status_code == 200:
                version_count = self.parse_version_list(list_resp.text)

        await self.upsert_package_snapshot(
            session,
            mapping_id,
            snapshot_date,
            latest_version=latest_version,
            version_count=version_count,
        )
        await session.commit()
