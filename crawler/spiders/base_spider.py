from abc import ABC, abstractmethod

from ..models.contract import CrawlResult


class BaseSpider(ABC):
    @abstractmethod
    async def crawl_ticker(self, symbol: str) -> CrawlResult:
        pass

    async def enrich(self, result: CrawlResult):
        new_data = await self.crawl_ticker(result.symbol)
        result.enrich(new_data)
