from abc import ABC, abstractmethod
from ..models.contract import CrawlResult

class BaseSpider(ABC):
    @abstractmethod
    def crawl_ticker(self, symbol: str) -> CrawlResult:
        pass

    def enrich(self, result: CrawlResult):
        """Enriches an existing CrawlResult by fetching missing data."""
        new_data = self.crawl_ticker(result.symbol)
        result.enrich(new_data)
