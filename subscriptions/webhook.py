import logging
from . import services

logger = logging.getLogger(__name__)

def dispatch(event: dict) -> None:

    handlers = {
        'customer.subscription.created': services.sync_from_stripe,
        'customer.subscription.updated': services.sync_from_stripe,
        'customer.subscription.deleted': lambda obj: services.handle_subscription_cancelled(obj['id']),
        'invoice.payment_failed': services.flag_payment_failed,
    }

    handler = handlers.get(event['type'])
    if not handler:
        return
    try:
        handler(event['data']['object'])
    except Exception:
        logger.exception(f'Error handling Stripe event {event["id"]} ({event["type"]})')