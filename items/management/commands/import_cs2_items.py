# items/management/commands/import_cs2_items.py
import requests
from django.core.management.base import BaseCommand
from django.utils import timezone
from items.models import Item, Marketplace, ItemListing


class Command(BaseCommand):
    help = 'Imports all CS2 items from Skinport API and seeds prices'

    def handle(self, *args, **kwargs):
        self.stdout.write('Fetching items from Skinport...')

        try:
            response = requests.get(
                'https://api.skinport.com/v1/items',
                params={'app_id': 730, 'currency': 'USD'},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f'Failed to fetch: {e}'))
            return

        self.stdout.write(f'Got {len(data)} items, importing...')

        skinport = Marketplace.objects.get(name='skinport')
        now = timezone.now()

        items_created = 0
        listings_created = 0

        for skin in data:
            name_on_market = skin.get('market_hash_name', '').strip()
            if not name_on_market:
                continue

            quality = None
            if '(' in name_on_market and name_on_market.endswith(')'):
                quality = name_on_market[name_on_market.rfind('(') + 1:-1]

            name = name_on_market[:name_on_market.rfind('(')].strip() if quality else name_on_market

            item, item_created = Item.objects.get_or_create(
                name_on_market=name_on_market,
                defaults={
                    'name': name,
                    'quality': quality,
                    'source_game': 'CS2',
                }
            )
            if item_created:
                items_created += 1

            # get price directly from API response
            min_price = skin.get('min_price')
            price = None
            if min_price:
                from decimal import Decimal
                price = Decimal(str(min_price))

            listing, listing_created = ItemListing.objects.get_or_create(
                item=item,
                marketplace=skinport,
                defaults={
                    'current_price': price,
                    'currency': 'USD',
                    'url': skin.get('item_page', ''),
                    'scrape_priority': 1,
                    'next_scrape_at': now,
                }
            )

            # update price if listing already existed
            if not listing_created and price:
                listing.current_price = price
                listing.url = skin.get('item_page', '') or listing.url
                listing.save()

            if listing_created:
                listings_created += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done — {items_created} items created, {listings_created} listings created'
        ))
