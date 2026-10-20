import logging
from datetime import datetime, timedelta, timezone as dt_timezone
from django.db import transaction
from django.utils import timezone
from .models import (
    UserSubscription, PromoCode, PromoCodeRedemption,
    SubscriptionTier, SubscriptionDuration, ProcessedStripeEvent,
)
from .models import PERIOD_KEYS
from .stripe_services import INTERVAL_TO_KEY

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {'active', 'trialing', 'past_due'}
DEACTIVATE_STATUSES = {'canceled', 'unpaid', 'incomplete_expired'}
IGNORE_STATUSES = {'incomplete'}

TIER_RANK = {SubscriptionTier.BASE: 1, SubscriptionTier.ADVANCED: 2}


def get_or_create_subscription(user) -> UserSubscription:
    sub, _ = UserSubscription.objects.get_or_create(
        user=user,
        defaults={'tier': SubscriptionTier.NONE, 'is_active': False},
    )
    return sub


def get_subscription(user) -> UserSubscription | None:
    try:
        return user.subscription
    except UserSubscription.DoesNotExist:
        return None


def has_base_access(user) -> bool:
    sub = get_subscription(user)
    return bool(sub and sub.has_base_access)


def has_advanced_access(user) -> bool:
    sub = get_subscription(user)
    return bool(sub and sub.has_advanced_access)


@transaction.atomic
def sync_from_stripe(stripe_sub: dict) -> UserSubscription | None:
    from users.models import User

    stripe_sub_id = stripe_sub.get('id')
    customer_id = stripe_sub.get('customer')
    status = stripe_sub.get('status')

    if not customer_id:
        logger.warning('Subscription %s has no customer', stripe_sub_id)
        return None

    try:
        user = User.objects.get(stripe_customer_id=customer_id)
    except User.DoesNotExist:
        logger.warning('No user found for Stripe customer %s', customer_id)
        return None

    if status in DEACTIVATE_STATUSES:
        logger.info('Deactivating subscription %s for customer: %s', stripe_sub_id, customer_id)
        return handle_subscription_cancelled(stripe_sub_id)

    if status in IGNORE_STATUSES:
        logger.info('Subscription %s is %s — waiting for confirmation',stripe_sub_id, status)
        return None

    if status not in ACTIVE_STATUSES:
        logger.warning('Unhandled status %s on subscription %s',status, stripe_sub_id )
        return None

    tier_key = stripe_sub.get('metadata', {}).get('tier')
    if not tier_key:
        logger.warning('Subscription %s has no tier metadata', stripe_sub_id)
        return None

    try:
        tier = SubscriptionTier(tier_key)
    except ValueError:
        logger.warning(f'Invalid tier "{tier_key}" on subscription {stripe_sub_id}')
        return None

    items = stripe_sub.get('items', {}).get('data', [])
    if not items or not items[0].get('current_period_end'):
        logger.warning(f'Subscription {stripe_sub_id} missing period end')
        return None

    recurring = items[0]['price']['recurring']
    interval_key = INTERVAL_TO_KEY.get(
        (recurring['interval_count'], recurring['interval'])
    )
    period_days = PERIOD_KEYS.get(interval_key[0]) if interval_key else None

    period_end = datetime.fromtimestamp(items[0]['current_period_end'], tz=dt_timezone.utc)

    sub, _ = UserSubscription.objects.update_or_create(
        user=user,
        defaults={
            'tier': tier,
            'is_active': True,
            'stripe_status': status,
            'current_period_end': period_end,
            'period_days': period_days,
            'stripe_subscription_id': stripe_sub_id,
            'cancelled_at': None,
        },
    )
    logger.info(f'Synced subscription for {user.email}: {tier} ({status}) until {period_end}')
    return sub

def is_downgrade(current_sub: UserSubscription | None, new_tier: SubscriptionTier, new_period_key: str) -> bool:
    if not current_sub or not current_sub.is_active:
        return False

    current_rank = TIER_RANK.get(current_sub.tier, 0)
    new_rank = TIER_RANK.get(new_tier, 0)

    if new_rank < current_rank:
        return True

    if new_rank == current_rank:
        new_days = PERIOD_KEYS.get(new_period_key)
        if current_sub.period_days and new_days and new_days < current_sub.period_days:
            return True

    return False

@transaction.atomic
def handle_subscription_cancelled(stripe_sub_id: str) -> UserSubscription | None:
    try:
        sub = UserSubscription.objects.get(stripe_subscription_id=stripe_sub_id)
    except UserSubscription.DoesNotExist:
        logger.warning(f'No local subscription for cancelled Stripe sub {stripe_sub_id}')
        return None

    sub.is_active = False
    sub.stripe_status = 'canceled'
    sub.cancelled_at = timezone.now()
    sub.save(update_fields=['is_active', 'stripe_status', 'cancelled_at'])
    return sub


def flag_payment_failed(invoice: dict) -> None:
    stripe_sub_id = invoice.get('subscription')
    if not stripe_sub_id:
        return
    try:
        sub = UserSubscription.objects.get(stripe_subscription_id=stripe_sub_id)
    except UserSubscription.DoesNotExist:
        return
    sub.stripe_status = 'past_due'
    sub.save(update_fields=['stripe_status'])
    logger.warning(f'Payment failed for subscription {stripe_sub_id}')



@transaction.atomic
def activate_from_promo(user, tier: SubscriptionTier, days: int) -> UserSubscription:
    if tier not in SubscriptionTier.values:
        raise ValueError(f'Invalid tier: {tier}')
    if days not in SubscriptionDuration.values:
        raise ValueError(f'Invalid duration: {days}')

    sub = get_or_create_subscription(user)
    sub.tier = tier
    sub.is_active = True
    sub.current_period_end = timezone.now() + timedelta(days=days)
    sub.stripe_subscription_id = None
    sub.stripe_status = ''
    sub.cancelled_at = None
    sub.period_days = days
    sub.save()
    return sub


def redeem_promo_code(user, code: str) -> tuple[bool, str]:
    normalized_code = code.strip()

    try:
        promo_code = PromoCode.objects.get(code=normalized_code)
    except PromoCode.DoesNotExist:
        return False, 'Promo code does not exist.'

    sub = get_subscription(user)

    if sub and sub.is_active:
        return False, 'You already have an active subscription.'

    if not promo_code.is_valid:
        return False, 'This promo code is expired or has reached its usage limit.'

    if PromoCodeRedemption.objects.filter(
        user=user,
        promo_code=promo_code,
    ).exists():
        return False, 'You have already used this promo code.'

    try:
        tier = SubscriptionTier(promo_code.tier)
    except ValueError:
        return False, 'Invalid subscription tier on promo code.'

    activate_from_promo(user, tier, promo_code.duration_days)

    promo_code.uses += 1
    promo_code.save(update_fields=['uses'])

    PromoCodeRedemption.objects.create(
        user=user,
        promo_code=promo_code,
    )

    logger.info(
        'Activated %s for %s days using promo code for user %s',
        tier.label,
        promo_code.duration_days,
        user.username,
    )

    return True, (
        f'Successfully activated {tier.label} '
        f'for {promo_code.duration_days} days.'
    )


def is_webhook_processed(event_id: str) -> bool:
    return ProcessedStripeEvent.objects.filter(
        event_id=event_id
    ).exists()


def mark_webhook_processed(event_id: str) -> None:
    ProcessedStripeEvent.objects.get_or_create(
        event_id=event_id
    )