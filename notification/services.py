from django.utils import timezone
from tracking.models import TrackedItem
from items.models import ItemListing
from notification.base import NotificationMessage
from notification.registry import registry


def check_price_alerts():
    tracked_items = (TrackedItem.objects
        .filter(user__isnull=False)
        .exclude(alert_min=None, alert_max=None)
        .select_related('user', 'item')
        .prefetch_related('marketplaces'))

    for tracked in tracked_items:
        listings = ItemListing.objects.filter(
            item=tracked.item,
            marketplace__in=tracked.marketplaces.all(),
            current_price__isnull=False,
        ).select_related('marketplace')

        for listing in listings:
            _check_listing_alert(tracked, listing)


def _check_listing_alert(tracked, listing):
    price = listing.current_price
    triggered = False
    direction = None

    if tracked.alert_min and price <= tracked.alert_min:
        triggered = True
        direction = 'below minimum'

    if tracked.alert_max and price >= tracked.alert_max:
        triggered = True
        direction = 'above maximum'

    if not triggered:
        return

    message = NotificationMessage(
        subject=f'Price alert: {tracked.item.name_on_market}',
        body=(
            f'{tracked.item.name_on_market} is {direction} on {listing.marketplace.name}\n'
            f'Current price: ${price}\n'
            f'Net price after fees: ${listing.net_price}\n'
            f'View: {listing.url}'
        ),
        user=tracked.user,
    )

    _send_notifications(tracked, message)


def _send_notifications(tracked, message):
    if tracked.notify_telegram:
        notifier = registry.get('telegram')
        if notifier:
            notifier.send(message)
