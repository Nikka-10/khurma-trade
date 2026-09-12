import stripe
from config import settings
from django.utils import timezone
from django.core.cache import cache
from datetime import datetime, timedelta, timezone as dt_timezone
from .models import UserSubscription, PromoCode, PromoCodeRedemption, SubscriptionTier, SubscriptionDuration,ProcessedStripeEvent
from users.models import User
from django.db import transaction


stripe.api_key = settings.STRIPE_TEST_SECRET_KEY

ACTIVE_STATUSES = {'active', 'trialing'}

INACTIVE_STATUSES = {
    'canceled',
    'unpaid',
    'incomplete_expired',
}

INTERVAL_TO_KEY = {
    (1, 'month'):  ('month',        '1 month',   SubscriptionDuration.MONTH),
    (3, 'month'):  ('three_months', '3 months',  SubscriptionDuration.THREE_MONTHS),
    (6, 'month'):  ('six_months',   '6 months',  SubscriptionDuration.HALF_YEAR),
    (1, 'year'):   ('year',         '1 year',    SubscriptionDuration.YEAR),
}

def get_plans_from_stripe() -> dict:
    cached = cache.get('stripe_plans')
    if cached:
        return cached

    products = stripe.Product.list(active=True)
    plans = {}

    for product in products.data:
        tier_key = product.name.lower()

        try:
            SubscriptionTier(tier_key)
        except ValueError:
            continue

        prices = stripe.Price.list(product=product.id, active=True)
        plan_prices = {}

        for price in prices.data:
            if not price.recurring:
                continue

            key_tuple = (price.recurring.interval_count, price.recurring.interval)
            mapping = INTERVAL_TO_KEY.get(key_tuple)
            if not mapping:
                continue
            key, label, days = mapping
            plan_prices[key] = {
                'id': price.id,
                'amount': price.unit_amount // 100,
                'label': label,
                'days': days,
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


def get_or_create_subscription(user: User) -> UserSubscription:
    sub, _ = UserSubscription.objects.get_or_create(
        user=user,
        defaults={
            'tier': SubscriptionTier.NONE,
            'is_active': False,
        }
    )
    return sub


def get_subscription(user) -> UserSubscription | None:
    try:
        return user.subscription
    except UserSubscription.DoesNotExist:
        return None


def has_base_access(user: User) -> bool:
    sub = get_subscription(user)
    if not sub:
        return False
    return sub.has_base_access


def has_advanced_access(user: User) -> bool:
    sub = get_subscription(user)
    if not sub:
        return False
    return sub.has_advanced_access


@transaction.atomic
def activate_subscription(user: User,
                          tier: SubscriptionTier,
                          period: int,
                          stripe_subscription_id: str | None = None,
                          ) -> UserSubscription:
    if tier not in SubscriptionTier.values:
        raise ValueError(f'Invalid tier: {tier}. Must be one of {SubscriptionTier.values}')

    if period not in SubscriptionDuration.values:
        raise ValueError(
            f'Invalid duration: {period}. '
            f'Must be one of {SubscriptionDuration.values}'
        )

    sub = get_or_create_subscription(user)
    sub.tier = tier
    sub.is_active = True
    sub.current_period_end = timezone.now() + timedelta(days=period)

    if stripe_subscription_id:
        sub.stripe_subscription_id = stripe_subscription_id

    sub.save()

    return sub


@transaction.atomic
def cancel_subscription(user) -> UserSubscription | None:
    sub = get_subscription(user)

    if not sub:
        return None

    if sub.stripe_subscription_id:
        try:
            stripe.Subscription.cancel(sub.stripe_subscription_id)
        except stripe.error.StripeError:
            pass

    sub.is_active = False
    sub.stripe_status = "canceled"
    sub.cancelled_at=timezone.now()
    sub.save()

    return sub


def handle_subscription_cancelled(stripe_sub_id: str) -> None:
    try:
        sub = UserSubscription.objects.get(stripe_subscription_id=stripe_sub_id)
        sub.is_active = False
        sub.cancelled_at = timezone.now()
        sub.save()
    except UserSubscription.DoesNotExist:
        pass


@transaction.atomic
def redeem_promo_code(user: User, code: str) -> tuple[bool, str]:
    try:
        promo_code = PromoCode.objects.get(code=code)
    except PromoCode.DoesNotExist:
        return False, "promo code does not exist"

    if not promo_code.is_valid:
        return False, 'This promo code is expired or has reached its usage limit.'

    already_used = PromoCodeRedemption.objects.filter(
        user = user,
        promo_code = promo_code
    ).exists()
    if already_used:
        return False, "promo code already used"

    try:
        tier = SubscriptionTier(promo_code.tier)
    except ValueError:
        return False, 'Invalid subscription tier on promo code.'

    activate_subscription(user, tier, promo_code.duration_days)
    promo_code.uses += 1
    promo_code.save()
    PromoCodeRedemption.objects.create(user=user, promo_code=promo_code)

    return True, f'Successfully activated {tier.label} for {promo_code.duration_days} days.'


@transaction.atomic
def sync_from_stripe(stripe_sub) -> UserSubscription | None:
    stripe_sub_id = stripe_sub['id']
    customer_id = stripe_sub.get('customer')
    status = stripe_sub.get('status')

    if not customer_id:
        print("stripe subscriptions has no customer")
        return None

    try:
        user = User.objects.get(
            stripe_customer_id=customer_id
        )
    except User.DoesNotExist:
        print("No user found for Stripe customer %s",)
        return None

    if status in INACTIVE_STATUSES:
        handle_subscription_cancelled(stripe_sub_id)
        return None

    if status not in ACTIVE_STATUSES:
        print("Ignoring Stripe subscription %s with status %s")
        return None

    tier_key = stripe_sub.get('metadata', {}).get('tier')

    if not tier_key:
        print("Stripe subscription %s has no tier metadata")
        return None

    try:
        tier = SubscriptionTier(tier_key)
    except ValueError:
        print("Invalid tier '%s' on Stripe subscription %s")
        return None

    items = stripe_sub.get('items', {}).get('data', [])

    if not items:
        print("Stripe subscription %s has no items")
        return None

    period_end_timestamp = items[0].get('current_period_end')

    if not period_end_timestamp:
        print("Stripe subscription %s has no current_period_end")
        return None

    period_end = datetime.fromtimestamp(
        period_end_timestamp,
        tz=dt_timezone.utc,
    )

    sub, _ = UserSubscription.objects.update_or_create(
        user=user,
        defaults={
            'tier': tier,
            'is_active': True,
            'stripe_status': status,
            'current_period_end': period_end,
            'stripe_subscription_id': stripe_sub_id,
            'cancelled_at': None,
        },
    )

    return sub


def upgrade_subscription(request, existing_sub_id, tier, price_data):
    existing_sub = stripe.Subscription.retrieve(existing_sub_id)
    return stripe.Subscription.modify(
        existing_sub_id,
        items=[{
            'id': existing_sub['items']['data'][0].id,
            'price': price_data['id'],
        }],
        proration_behavior='always_invoice',
        metadata={
            'user_id': request.user.id,
            'tier': tier,
        }
    )


def create_checkout_session(
    user,
    customer_id,
    price_id,
    tier,
    success_url,
    cancel_url,
):
    return stripe.checkout.Session.create(
        mode='subscription',
        customer=customer_id,
        line_items=[
            {
                'price': price_id,
                'quantity': 1,
            }
        ],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            'user_id': str(user.id),
        },
        subscription_data={
            'metadata': {
                'user_id': str(user.id),
                'tier': tier,
            },
        },
    )

def create_stripe_customer(user):
    customer = stripe.Customer.create(
        email=user.email,
        metadata={'user_id': user.id}
    )
    user.stripe_customer_id = customer.id
    user.save()
    return customer

def mark_webhook_processed(event_id):
    _, created = ProcessedStripeEvent.objects.get_or_create(event_id=event_id)
    return created







