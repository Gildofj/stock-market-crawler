from abc import ABC, abstractmethod

from ..services.data_service import DataService


class BaseSpider(ABC):
    def __init__(self, data_service: DataService):
        self.data_service = data_service

    @abstractmethod
    def crawl_ticker(self, symbol: str):
        pass
