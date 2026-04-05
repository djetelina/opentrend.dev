import logging
import re
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

import niquests

from opentrend import USER_AGENT
from opentrend.metrics import instrumented_client
from opentrend.collectors.base import PackageCollector

logger = logging.getLogger(__name__)

AUR_API = "https://aur.archlinux.org/rpc/v5"


class AURCollector(PackageCollector):
    @staticmethod
    def parse_aur(data: dict) -> dict | None:
        results = data.get("results", [])
        if not results:
            return None
        pkg = results[0]
        return {
            "version": pkg["Version"],
            "votes": pkg["NumVotes"],
            "popularity": pkg["Popularity"],
            "out_of_date": pkg["OutOfDate"] is not None,
        }

    async def collect(
        self, session: AsyncSession, mapping_id: int, snapshot_date: date
    ) -> None:
        mapping = await self.get_mapping(session, mapping_id)

        async with instrumented_client(headers={"User-Agent": USER_AGENT}) as client:
            resp = await client.get(
                f"{AUR_API}/info/{mapping.package_name}",
            )
            resp.raise_for_status()
            info = self.parse_aur(resp.json())

        if info is None:
            return

        # Scrape "Required by" count from AUR package page
        dependents_count = None
        try:
            async with instrumented_client(
                timeout=15, headers={"User-Agent": USER_AGENT}
            ) as web_client:
                page_resp = await web_client.get(
                    f"https://aur.archlinux.org/packages/{mapping.package_name}",
                )
                if page_resp.status_code == 200:
                    match = re.search(r"Required by \((\d+)\)", page_resp.text)
                    if match:
                        dependents_count = int(match.group(1))
        except niquests.exceptions.RequestException, KeyError, ValueError, TypeError:
            logger.warning(
                "Failed to scrape AUR dependents for %s",
                mapping.package_name,
                exc_info=True,
            )

        await self.upsert_package_snapshot(
            session,
            mapping_id,
            snapshot_date,
            latest_version=info["version"],
            votes=info["votes"],
            popularity=info["popularity"],
            dependents_count=dependents_count,
        )
        await session.commit()
