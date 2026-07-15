# scraper/services.py
from django.utils import timezone
from django.db import transaction
from items.models import ItemListing
from scraper.registry import registry
from scraper.config import SCRAPE_INTERVALS, PRIORITY_LEVELS, BATCH_SIZE


def scrape_due_listings():
    now = timezone.now()

    listings = (ItemListing.objects
        .filter(
            scrape_priority__gt=PRIORITY_LEVELS['none'],
            next_scrape_at__lte=now,
        )
        .select_related('item', 'marketplace')
        .order_by('-scrape_priority')[:BATCH_SIZE])

    by_marketplace = {}
    for listing in listings:
        name = listing.marketplace.name.lower()
        by_marketplace.setdefault(name, []).append(listing)

    updated_count = 0
    for marketplace_name, marketplace_listings in by_marketplace.items():
        scraper = registry.get(marketplace_name)
        if not scraper:
            continue

        item_names = [l.item.name_on_market for l in marketplace_listings]
        results = scraper.get_prices_bulk(item_names)
        result_map = {r.item_name: r for r in results}

        with transaction.atomic():
            for listing in marketplace_listings:
                result = result_map.get(listing.item.name_on_market)
                if not result or not result.success:
                    continue

                price_changed = listing.current_price != result.price
                listing.current_price = result.price
                if result.url:
                    listing.url = result.url
                if price_changed:
                    listing.price_changed_at = now

                interval = _get_interval(listing.scrape_priority)
                listing.next_scrape_at = now + interval
                listing.save()
                updated_count += 1

    return updated_count


def _get_interval(priority):
    if priority >= PRIORITY_LEVELS['high']:
        return SCRAPE_INTERVALS['high']
    elif priority >= PRIORITY_LEVELS['medium']:
        return SCRAPE_INTERVALS['medium']
    return SCRAPE_INTERVALS['low']