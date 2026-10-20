import logging
from . import services

logger = logging.getLogger(__name__)


def dispatch(event: dict) -> None:
    handlers = {
        'customer.subscription.created': services.sync_from_stripe,
        'customer.subscription.updated': services.sync_from_stripe,
        'customer.subscription.deleted': (lambda obj: services.handle_subscription_cancelled(obj['id'])),
        'invoice.payment_failed': services.flag_payment_failed,
    }

    event_type = event['type']
    event_id = event['id']

    handler = handlers.get(event_type)

    if handler is None:
        logger.debug('Ignoring unsupported Stripe event %s (%s)',event_id, event_type,)
        return

    try:
        handler(event['data']['object'])
    except Exception:
        logger.exception('Failed to process Stripe event %s (%s)', event_id, event_type,)
        raise

    logger.info('Successfully processed Stripe event %s (%s)',event_id,event_type,)
