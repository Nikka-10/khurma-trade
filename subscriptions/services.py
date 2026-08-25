from django.utils import timezone
from datetime import timedelta
from .models import UserSubscription, PromoCode, PromoCodeRedemption, SubscriptionTier, SubscriptionDuration
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

    sub.is_active = False
    sub.cancelled_at=timezone.now()
    sub.save()

    return sub


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


def sync_from_stripe(stripe_subscription) -> UserSubscription | None:
    try:
        customer = stripe_subscription.customer
        user = User.objects.get(email=customer.email)
    except User.DoesNotExist:
        return None

    tier = _get_tier_from_stripe(stripe_subscription)
    days = _get_days_remining(stripe_subscription)

    sub = activate_subscription(
        user=user,
        tier=tier,
        period=days,
        stripe_subscription_id=stripe_subscription.id
    )
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








