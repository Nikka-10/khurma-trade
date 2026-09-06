import stripe
from config import settings
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta, timezone as dt_timezone
from .models import UserSubscription, PromoCode, PromoCodeRedemption, SubscriptionTier, SubscriptionDuration
from users.models import User


stripe.api_key = settings.STRIPE_TEST_SECRET_KEY


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
    )
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


def sync_from_stripe(stripe_sub) -> UserSubscription | None:
    try:
        user = User.objects.get(stripe_customer_id=stripe_sub['customer'])
    except User.DoesNotExist:
        return None

    if (status := stripe_sub.get('status')) not in ('active', 'trialing'):
        handle_subscription_cancelled(stripe_sub['id'])
        return None


    if not (tier_key := stripe_sub['metadata'].get('tier')):
        price_id = stripe_sub['items']['data'][0]['price']['id']
        price = stripe.Price.retrieve(price_id, expand=['product'])
        tier_key = price.product.name.lower()

    product_id = stripe_sub['items']['data'][0]['price']['product']
    product = stripe.Product.retrieve(product_id)
    tier_key = product.name.lower()

    try:
        tier = SubscriptionTier(tier_key)
    except ValueError:
        return None

    import datetime
    period_end = datetime.datetime.fromtimestamp(
        stripe_sub['items']['data'][0]['current_period_end'],
        tz=dt_timezone.utc
    )

    sub = get_or_create_subscription(user)
    sub.tier = tier
    sub.is_active = True
    sub.current_period_end = period_end
    sub.stripe_subscription_id = stripe_sub['id']
    sub.cancelled_at = None
    sub.save()

    return sub



def _get_tier_from_stripe(stripe_subscription) -> SubscriptionTier:
    product_name = stripe_subscription.plan.product.name.lower()
    if 'advanced' in product_name:
        return SubscriptionTier.ADVANCED
    return SubscriptionTier.BASE


def _get_days_remining(stripe_subscription) -> int:
    from django.utils import timezone
    end = stripe_subscription.current_period_end
    delta = end - timezone.now()
    return max(delta.days, 0)


def create_subscription_intent(request, customer_id, tier, price_data):
    return stripe.Subscription.create(
            customer=customer_id,
            items=[{'price': price_data['id']}],
            payment_behavior='default_incomplete',
            payment_settings={'save_default_payment_method': 'on_subscription'},
            expand=['latest_invoice.confirmation_secret'],
            metadata={
                'user_id': request.user.id,
                'tier': tier,
            }
        )








