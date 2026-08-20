from django.db import models
from users.models import User
from django.utils import timezone



class SubscriptionTier(models.TextChoices):
    BASE = 'Base', 'base'
    ADVANCED = 'Advanced', 'advanced'


class UserSubscription(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')
    tier = models.CharField(max_length=20, choices=SubscriptionTier.choices, default=SubscriptionTier.BASE)

    stripe_subscription_id = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=False)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['user', 'is_active']),]

    def __str__(self):
        return f'{self.user.email} — {self.tier}'

    @property
    def is_expired(self) -> bool:
        if not self.current_period_end:
            return True
        return timezone.now() > self.current_period_end

    @property
    def has_base_access(self) -> bool:
        return self.is_active and not self.is_expired

    @property
    def has_advanced_access(self) -> bool:
        return (self.is_active
                and not self.is_expired
                and self.tier == SubscriptionTier.ADVANCED)



class PromoCode(models.Model):
    code = models.CharField(max_length=10, unique=True)
    tier = models.CharField(max_length=20, choices=SubscriptionTier.choices)
    duration_days = models.PositiveIntegerField()
    max_uses = models.IntegerField(default=0)
    uses = models.IntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_valid(self) -> bool:
        if self.uses >= self.max_uses:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True

    def __str__(self):
        return f'{self.code} — {self.tier} ({self.duration_days} days)'


class PromoCodeRedemption(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    promo_code = models.ForeignKey(PromoCode, on_delete=models.CASCADE)
    redeemed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'promo_code')
