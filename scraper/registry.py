import importlib
import pkgutil
from . import scrappers
from .base import BaseScraper


class ScraperRegistry:
    def __init__(self):
        self._scrapers: dict[str, BaseScraper] = {}
        self._discover()

    def _discover(self):
        for _, module_name, _ in pkgutil.iter_modules(scrappers.__path__):
            module = importlib.import_module(f"scraper.scrappers.{module_name}")
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type)
                        and issubclass(attr, BaseScraper)
                        and attr is not BaseScraper):
                    instance = attr()
                    self._scrapers[instance.marketplace_name] = instance

    def get(self, marketplace_name: str) -> BaseScraper | None:
        return self._scrapers.get(marketplace_name)

    def all(self) -> list[BaseScraper]:
        return list(self._scrapers.values())

    @property
    def available(self) -> list[str]:
        return list(self._scrapers.keys())


registry = ScraperRegistry()