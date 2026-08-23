from django.utils import timezone
from datetime import timedelta
from .models import UserSubscription, PromoCode, PromoCodeRedemption, SubscriptionTier
from users.models import User



def get_or_create_subscription(user: User) -> UserSubscription:
    sub, _ = UserSubscription.objects.get_or_create(
        user=user,
        defaults={
            'tier': None,
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
                          period: int) -> UserSubscription:
    if tier not in SubscriptionTier.values:
        raise ValueError(f'Invalid tier: {tier}. Must be one of {SubscriptionTier.values}')

    sub = get_or_create_subscription(user)
    sub.tier = tier
    sub.is_active = True
    sub.current_period_end = timezone.now() + timedelta(days=period)
    sub.save()

    return sub


def cancel_subscription(user) -> UserSubscription | None:
    sub = get_subscription(user)

    if not sub:
        return None

    sub.is_active = False
    sub.cancelled_at=timezone.now()
    sub.save()

    return sub


def redeem_promo_code(user: User, code: str):
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



