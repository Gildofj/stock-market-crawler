from __future__ import annotations

from loguru import logger

from crawler.models.contract import CrawlResult
from crawler.spiders.cvm_spider import CVMSpider

from .logo_service import LogoService
from .metadata_overrides import get_override


class MetadataResolver:
    def __init__(self, cvm_spider: CVMSpider, logo_service: LogoService) -> None:
        self.cvm_spider = cvm_spider
        self.logo_service = logo_service
        self._cvm_sector_map: dict[str, str] | None = None

    async def apply(self, result: CrawlResult) -> None:
        override = get_override(result.symbol)

        if result.sector is None:
            result.sector = self._lookup_cvm_sector(result.symbol) or override.get("sector")
        if result.sub_sector is None:
            result.sub_sector = override.get("sub_sector")
        if result.segment is None:
            result.segment = override.get("segment")

        if result.logo_url is None:
            try:
                result.logo_url = await self.logo_service.resolve(
                    result.symbol, result.website
                )
            except Exception as exc:
                logger.warning(f"logo resolve failed for {result.symbol}: {exc}")

    def _lookup_cvm_sector(self, symbol: str) -> str | None:
        cvm_code = self.cvm_spider.get_cvm_code(symbol)
        if cvm_code is None:
            return None
        if self._cvm_sector_map is None:
            self._cvm_sector_map = self.cvm_spider.dataset_service.get_sector_by_cvm_code()
        return self._cvm_sector_map.get(cvm_code)
