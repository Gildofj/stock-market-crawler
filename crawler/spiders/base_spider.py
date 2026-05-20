from abc import ABC, abstractmethod

from ..models.contract import CrawlResult


class BaseSpider(ABC):
    @abstractmethod
    async def crawl_ticker(self, symbol: str) -> CrawlResult:
        """Asynchronously crawls a ticker."""
        pass

    async def enrich(self, result: CrawlResult):
        """Asynchronously enriches an existing CrawlResult by fetching missing data."""
        new_data = await self.crawl_ticker(result.symbol)
        result.enrich(new_data)
