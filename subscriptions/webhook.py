import logging
from . import services
import stripe
from django.conf import settings

logger = logging.getLogger(__name__)

def verify_event(payload, signature):
    return stripe.Webhook.construct_event(
        payload,
        signature,
        settings.DJSTRIPE_WEBHOOK_SECRET
    )

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

    handler(event['data']['object'])