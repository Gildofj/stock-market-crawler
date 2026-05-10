from abc import ABC, abstractmethod

from ..models.contract import CrawlResult


class BaseSpider(ABC):
    @abstractmethod
    def crawl_ticker(self, symbol: str) -> CrawlResult:
        """Synchronously crawls a ticker."""
        pass

    @abstractmethod
    async def crawl_ticker_async(self, symbol: str) -> CrawlResult:
        """Asynchronously crawls a ticker."""
        pass

    def enrich(self, result: CrawlResult):
        """Enriches an existing CrawlResult by fetching missing data."""
        new_data = self.crawl_ticker(result.symbol)
        result.enrich(new_data)

    async def enrich_async(self, result: CrawlResult):
        """Asynchronously enriches an existing CrawlResult."""
        new_data = await self.crawl_ticker_async(result.symbol)
        result.enrich(new_data)
