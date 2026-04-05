import logging
from xml.etree.ElementTree import ParseError

from defusedxml.ElementTree import fromstring as defused_fromstring
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from opentrend import USER_AGENT
from opentrend.metrics import instrumented_client
from opentrend.collectors.base import PackageCollector

logger = logging.getLogger(__name__)

CHOCOLATEY_API = "https://community.chocolatey.org/api/v2"

# OData namespace
NS_D = "http://schemas.microsoft.com/ado/2007/08/dataservices"
NS_M = "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"


class ChocolateyCollector(PackageCollector):
    @staticmethod
    def parse_package(xml_text: str) -> dict | None:
        try:
            root = defused_fromstring(xml_text)
        except ParseError:
            logger.warning("Chocolatey XML parse failed", exc_info=True)
            return None

        # Find properties element
        for props in root.iter(f"{{{NS_M}}}properties"):
            version = None
            download_count = None
            for child in props:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag == "Version" and child.text:
                    version = child.text
                elif tag == "DownloadCount" and child.text:
                    try:
                        download_count = int(child.text)
                    except ValueError:
                        pass

            if version:
                return {
                    "latest_version": version,
                    "downloads_total": download_count,
                }
        return None

    async def collect(
        self, session: AsyncSession, mapping_id: int, snapshot_date: date
    ) -> None:
        mapping = await self.get_mapping(session, mapping_id)

        async with instrumented_client(headers={"User-Agent": USER_AGENT}) as client:
            # OData $filter/$top must be literal $ in the URL, not %24
            safe_name = mapping.package_name.replace("'", "''")
            url = f"{CHOCOLATEY_API}/Packages()?$filter=Id eq '{safe_name}' and IsLatestVersion&$top=1"
            resp = await client.get(url)
            if resp.status_code == 404:
                return
            resp.raise_for_status()
            info = self.parse_package(resp.text)

        if info is None:
            return

        await self.upsert_package_snapshot(
            session,
            mapping_id,
            snapshot_date,
            **info,
        )
        await session.commit()
