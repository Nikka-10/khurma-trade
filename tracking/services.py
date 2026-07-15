from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from items.models import Item ,ItemListing, Marketplace
from scraper.registry import registry
from .models import TrackedItem



def item_prices(item, selected_marketplace_ids=None):
    STALE_AFTER = timedelta(hours=1)
    now = timezone.now()

    listings = ItemListing.objects.filter(item=item).select_related('marketplace')

    if selected_marketplace_ids:
        listings = listings.filter(marketplace_id__in=selected_marketplace_ids)

    fresh = [] # not using currently
    stale = []
    for listing in listings:
        if listing.last_checked_at and now - listing.last_checked_at < STALE_AFTER:
            fresh.append(listing)
        else:
            stale.append(listing)

    if stale:
        _scrape_listings(stale, now)

        listings = ItemListing.objects.filter(item=item).select_related('marketplace')
        if selected_marketplace_ids:
            listings = listings.filter(marketplace_id__in=selected_marketplace_ids)

    return listings


def _scrape_listings(listings, now):
    by_marketplace = {}

    for listing in listings:
        name = listing.marketplace.name.lower()
        by_marketplace.setdefault(name, []).append(listing)

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
                listing.next_scrape_at = now + timedelta(hours=1)
                listing.save()


def get_tracked_items(user_id):
    return (TrackedItem.objects
     .filter(user=user_id)
     .select_related('item')
     .prefetch_related('marketplaces'))


def add_tracked_items(user_id, item, alert_min, alert_max):
    tracked, created = TrackedItem.objects.get_or_create(
        user=user_id,
        item=item,
        defaults={
            'alert_min': alert_min,
            'alert_max': alert_max,
        })
    return tracked, created


def remove_tracked_items(user_id, item_id):
    TrackedItem.objects.filter(user=user_id, item_id=item_id).delete()