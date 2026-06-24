# scraper/base.py
from abc import ABC, abstractmethod
from decimal import Decimal
from dataclasses import dataclass
from typing import Optional


@dataclass
class ScrapeResult:
    item_name: str
    price: Decimal
    currency: str
    url: str
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None


class BaseScraper(ABC):

    @property
    @abstractmethod
    def marketplace_name(self) -> str:

        pass

    @abstractmethod
    def get_price(self, item_name: str) -> ScrapeResult:

        pass

    def get_prices_bulk(self, item_names: list[str]) -> list[ScrapeResult]:
        """
        Fetch prices for multiple items.
        Default implementation just calls get_price in a loop.
        Override this if the marketplace has a bulk API endpoint.
        """
        return [self.get_price(name) for name in item_names]