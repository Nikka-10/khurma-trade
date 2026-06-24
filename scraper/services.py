from django.utils import timezone
from items.models import ItemListing
from tradebook.models import TradeBook
from .config import SCRAPE_INTERVALS, PRIORITY_LEVELS, BATCH_SIZE
from items.models import ItemListing, Marketplace
from scraper.register_scrapper import registry



def scrape_due_listings():
    """Called by Celery task — scrapes all listings due for update"""
    now = timezone.now()

    listings = (ItemListing.objects
        .filter(
            scrape_priority__gt=PRIORITY_LEVELS['none'],
            next_scrape_at__lte=now,
        )
        .select_related('item', 'marketplace')
        .order_by('-scrape_priority')[:BATCH_SIZE])

    # group listings by marketplace
    by_marketplace: dict[str, list] = {}
    for listing in listings:
        name = listing.marketplace.name.lower()
        by_marketplace.setdefault(name, []).append(listing)

    for marketplace_name, marketplace_listings in by_marketplace.items():
        scraper = registry.get(marketplace_name)
        if not scraper:
            continue  # no scraper for this marketplace yet

        item_names = [l.item.name_on_market for l in marketplace_listings]
        results = scraper.get_prices_bulk(item_names)

        # build result lookup
        result_map = {r.item_name: r for r in results}

        with transaction.atomic():
            for listing in marketplace_listings:
                result = result_map.get(listing.item.name_on_market)
                if not result or not result.success:
                    continue

                price_changed = listing.current_price != result.price

                listing.current_price = result.price
                listing.url = result.url or listing.url
                if price_changed:
                    listing.price_changed_at = now

                # schedule next scrape based on priority
                interval = _get_interval(listing.scrape_priority)
                listing.next_scrape_at = now + interval
                listing.save()


def _get_interval(priority: int):
    if priority >= PRIORITY_LEVELS['high']:
        return SCRAPE_INTERVALS['high']
    elif priority >= PRIORITY_LEVELS['medium']:
        return SCRAPE_INTERVALS['medium']
    return SCRAPE_INTERVALS['low']
def recalculate_priorities():
    now = timezone.now()

    # medium — items in tradebooks
    tradebook_item_ids = (TradeBook.objects
        .values_list('item_id', flat=True)
        .distinct())

    ItemListing.objects.filter(
        item_id__in=tradebook_item_ids
    ).update(
        scrape_priority=PRIORITY_LEVELS['medium'],
        next_scrape_at=now
    )

    # everything else — won't be scraped
    ItemListing.objects.exclude(
        item_id__in=tradebook_item_ids
    ).update(scrape_priority=PRIORITY_LEVELS['none'])