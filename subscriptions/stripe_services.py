import stripe
from django.conf import settings

stripe.api_key = settings.STRIPE_TEST_SECRET_KEY

INTERVAL_TO_KEY = {
    (1, 'month'): ('month', '1 month'),
    (3, 'month'): ('three_months', '3 months'),
    (6, 'month'): ('six_months', '6 months'),
    (1, 'year'):  ('year', '1 year'),
}


def verify_webhook_event(payload: bytes, sig_header: str):
    return stripe.Webhook.construct_event(
        payload, sig_header, settings.DJSTRIPE_WEBHOOK_SECRET
    )


def get_plans() -> dict:
    from django.core.cache import cache
    from .models import SubscriptionTier

    cached = cache.get('stripe_plans')
    if cached:
        return cached

    plans = {}
    for product in stripe.Product.list(active=True).data:
        tier_key = product.name.lower()
        try:
            SubscriptionTier(tier_key)
        except ValueError:
            continue

        plan_prices = {}
        for price in stripe.Price.list(product=product.id, active=True).data:
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
    return plans


def create_customer(user):
    customer = stripe.Customer.create(email=user.email, metadata={'user_id': user.id})
    user.stripe_customer_id = customer.id
    user.save(update_fields=['stripe_customer_id'])
    return customer


def get_or_create_customer_id(user) -> str:
    if user.stripe_customer_id:
        try:
            customer = stripe.Customer.retrieve(user.stripe_customer_id)

            if not customer.get('deleted'):
                return customer.id

        except stripe.error.StripeError:
            pass

    return create_customer(user).id


def start_checkout(user, price_id: str, tier: str, success_url: str, cancel_url: str):
    customer_id = get_or_create_customer_id(user)
    return stripe.checkout.Session.create(
        mode='subscription',
        customer=customer_id,
        line_items=[{'price': price_id, 'quantity': 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        subscription_data={'metadata': {'user_id': str(user.id), 'tier': tier}},
    )


def upgrade_subscription(user, stripe_subscription_id: str, price_id: str, tier: str):
    existing = stripe.Subscription.retrieve(stripe_subscription_id)
    return stripe.Subscription.modify(
        stripe_subscription_id,
        items=[{'id': existing['items']['data'][0].id, 'price': price_id}],
        proration_behavior='always_invoice',
        metadata={'user_id': str(user.id), 'tier': tier},
    )


def request_cancellation(stripe_subscription_id: str) -> bool:
    try:
        stripe.Subscription.cancel(stripe_subscription_id)
        return True
    except stripe.error.StripeError:
        return False