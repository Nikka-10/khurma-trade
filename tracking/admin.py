from django.contrib import admin
from .models import TrackedItem


@admin.register(TrackedItem)
class TrackedItemAdmin(admin.ModelAdmin):
    list_display = ['user', 'item', 'alert_min', 'alert_max', 'notify_telegram', 'created_at']
    list_filter = ['notify_telegram']
    search_fields = ['user__email', 'item__name_on_market']
    filter_horizontal = ['marketplaces']