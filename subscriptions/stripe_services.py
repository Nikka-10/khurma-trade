import stripe
from django.conf import settings
import logging
from subscriptions.exceptions import StaleStripeReferenceError
from . import exceptions

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_TEST_SECRET_KEY
stripe.max_network_retries = 3

INTERVAL_TO_KEY = {
    (1, 'month'): ('month', '1 month'),
    (3, 'month'): ('three_months', '3 months'),
    (6, 'month'): ('six_months', '6 months'),
    (1, 'year'):  ('year', '1 year'),
}


def verify_webhook_event(payload: bytes, sig_header: str):
    try:
        return stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.DJSTRIPE_WEBHOOK_SECRET,
        )
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        logger.error('Failed to verify webhook event: %s', e)
        raise exceptions.InvalidWebhookError() from e


def get_plans() -> dict:
    from django.core.cache import cache
    from .models import SubscriptionTier

    cached = cache.get('stripe_plans')
    if cached is not None:
        return cached
    try:
        plans = {}
        products = stripe.Product.list(active=True)
        for product in products.auto_paging_iter():
            tier_key = product.metadata.get('tier')
            try:
                SubscriptionTier(tier_key)
            except ValueError:
                logger.warning('skipped SubscriptionTier for product %s',product.name, )
                continue

            plan_prices = {}
            prices = stripe.Price.list(product=product.id, active=True)
            for price in prices.auto_paging_iter():
                if not price.recurring:
                    continue
                mapping = INTERVAL_TO_KEY.get(
                    (price.recurring.interval_count, price.recurring.interval)
                )
                if not mapping:
                    continue
                key, label = mapping
                plan_prices[key] = {
                    'id': price.id,
                    'amount': price.unit_amount // 100,
                    'label': label,
                }

            plans[tier_key] = {
                'name': product.name,
                'description': product.description or '',
                'prices': plan_prices,
                'tier': SubscriptionTier(tier_key),
            }

        plans = dict(sorted(plans.items()))
        cache.set('stripe_plans', plans, timeout=3600)
        if not plans:
            logger.warning('plans are empty')

        return plans
    except stripe.error.StripeError as e:
        logger.error('Failed to load Stripe plans: %s', e)
        raise exceptions.PaymentServiceError(
            'Failed to load Stripe plans.'
        ) from e


def create_customer(user):
    try:
        customer = stripe.Customer.create(email=user.email, metadata={'user_id': user.id})
    except stripe.error.StripeError as e:
        logger.error('failed to create customer for user %s: %s', user.id, e)
        raise
    user.stripe_customer_id = customer.id
    user.save(update_fields=['stripe_customer_id'])

    return customer


def get_or_create_customer_id(user) -> str:
    if user.stripe_customer_id:
        try:
            customer = stripe.Customer.retrieve(user.stripe_customer_id)
            if not customer.get('deleted'):
                return customer.id
        except stripe.error.InvalidRequestError:
            logger.warning(
            'Stale Stripe customer id for user %s: %s, creating a new one',
            user.id, user.stripe_customer_id,
            )

    return create_customer(user).id


def start_checkout(user, price_id: str, tier: str, success_url: str, cancel_url: str):
    customer_id = get_or_create_customer_id(user)

    try:
        return stripe.checkout.Session.create(
            mode='subscription',
            customer=customer_id,
            line_items=[{'price': price_id, 'quantity': 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            subscription_data={'metadata': {'user_id': str(user.id), 'tier': tier}},
        )
    except stripe.error.StripeError as e:
        logger.error(
            'Failed to start checkout for user %s with price %s: %s',
            user.id,
            price_id,
            e,
        )
        raise


def upgrade_subscription(user, stripe_subscription_id: str, price_id: str, tier: str):
    try:
        existing = stripe.Subscription.retrieve(stripe_subscription_id)
    except stripe.error.InvalidRequestError as e:
        logger.error(
            'Stale subscription reference for user %s: %s — %s',
            user.id,
            stripe_subscription_id,
            e,
        )
        raise StaleStripeReferenceError from e

    if existing['customer'] != user.stripe_customer_id:
        logger.error('this subscription does not belong to user %s', user.id)
        raise StaleStripeReferenceError()

    try:
        return stripe.Subscription.modify(
            stripe_subscription_id,
            items=[{'id': existing['items']['data'][0].id, 'price': price_id}],
            proration_behavior='always_invoice',
            metadata={'user_id': str(user.id), 'tier': tier},
        )
    except stripe.error.CardError as e:
        logger.warning('Card declined during upgrade for user %s: %s', user.id, e.user_message )
        raise
    except stripe.error.StripeError as e:
        logger.error('Stripe error during upgrade for user %s: %s', user.id, e)
        raise


def request_cancellation(stripe_subscription_id: str) -> bool:
    try:
        stripe.Subscription.cancel(stripe_subscription_id)
        return True
    except stripe.error.InvalidRequestError:
        logger.info('Cancellation requested for already-gone subscription %s', stripe_subscription_id)
        raise
    except stripe.error.StripeError as e:
        logger.error('Failed to cancel subscription %s : %s', stripe_subscription_id, e)
        raise