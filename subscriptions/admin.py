from django.contrib import admin
from .models import UserSubscription, PromoCode, PromoCodeRedemption

@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'tier', 'is_active', 'current_period_end']
    list_filter = ['tier', 'is_active']
    search_fields = ['user__email']


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'tier', 'duration_days', 'uses', 'max_uses', 'expires_at', 'is_valid']
    search_fields = ['code']


@admin.register(PromoCodeRedemption)
class PromoCodeRedemptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'promo_code', 'redeemed_at']
