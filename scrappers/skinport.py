# scrappers/skinport.py
import requests
from decimal import Decimal
from scraper.base_scrapper import BaseScraper, ScrapeResult


class SkinportScraper(BaseScraper):

    BASE_URL = 'https://api.skinport.com/v1'
    CURRENCY = 'USD'

    @property
    def marketplace_name(self) -> str:
        return 'skinport'

    def get_prices_bulk(self, item_names: list[str]) -> list[ScrapeResult]:
        try:
            response = requests.get(
                f"{self.BASE_URL}/items",
                params={
                    "app_id": 730,
                    "currency": self.CURRENCY,
                },
                headers={
                    "Accept-Encoding": "br",
                    "User-Agent": "KhurmaTrade/1.0",
                },
                timeout=30,
            )
            response.raise_for_status()
            print("Status:", response.status_code)
            print("Content-Type:", response.headers.get("Content-Type"))
            print("Text:", repr(response.text[:500]))
            data = response.json()

        except requests.Timeout:
            return [ScrapeResult(name, Decimal('0'), self.CURRENCY, '', error='Timeout') 
                    for name in item_names]
        except requests.RequestException as e:
            return [ScrapeResult(name, Decimal('0'), self.CURRENCY, '', error=str(e)) 
                    for name in item_names]

        # build lookup dict from response for O(1) access
        price_map = {
            item['market_hash_name']: item for item in data
        }

        results = []
        for name in item_names:
            item_data = price_map.get(name)

            if not item_data:
                results.append(ScrapeResult(
                    item_name=name,
                    price=Decimal('0'),
                    currency=self.CURRENCY,
                    url='',
                    error=f'Item "{name}" not found on Skinport'
                ))
                continue

            # skinport returns prices in cents
            min_price = item_data.get('min_price') or item_data.get('suggested_price')
            if not min_price:
                results.append(ScrapeResult(
                    item_name=name,
                    price=Decimal('0'),
                    currency=self.CURRENCY,
                    url='',
                    error='No price available'
                ))
                continue

            results.append(ScrapeResult(
                item_name=name,
                price=Decimal(str(min_price / 100)),  # convert cents to dollars
                currency=self.CURRENCY,
                url=item_data.get("item_page", ""),
            ))

        return results

    def get_price(self, item_name: str) -> ScrapeResult:
        # skinport bulk is more efficient even for single items
        # since it fetches everything in one request anyway
        results = self.get_prices_bulk([item_name])
        return results[0]