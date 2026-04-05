import logging
from datetime import date

import niquests
from sqlalchemy.ext.asyncio import AsyncSession

from opentrend import USER_AGENT
from opentrend.distro_fetchers import FETCHERS, make_github_raw
from opentrend.metrics import instrumented_client
from opentrend.collectors.base import PackageCollector

logger = logging.getLogger(__name__)


class DistroCollector(PackageCollector):
    """Collector for distro packages — presence and version only."""

    def __init__(self, github_token: str | None = None) -> None:
        self._github_token = github_token

    async def collect(
        self, session: AsyncSession, mapping_id: int, snapshot_date: date
    ) -> None:
        mapping = await self.get_mapping(session, mapping_id)

        fetcher = FETCHERS.get(mapping.source)
        if fetcher is None:
            logger.warning("No fetcher for source %s", mapping.source)
            return

        async with instrumented_client(headers={"User-Agent": USER_AGENT}) as client:
            github_raw = make_github_raw(client, self._github_token)
            try:
                info = await fetcher(
                    client,
                    mapping.package_name,
                    github_raw=github_raw,
                )
            except niquests.exceptions.RequestException:
                logger.warning(
                    "Distro fetch failed for %s/%s",
                    mapping.source,
                    mapping.package_name,
                    exc_info=True,
                )
                return

        if info is None:
            return

        await self.upsert_package_snapshot(
            session,
            mapping_id,
            snapshot_date,
            **info,
        )
        await session.commit()
