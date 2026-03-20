from django.contrib import admin
from .models import tradebook


@admin.register(tradebook)
class TradebookAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'item_listing', 'purchase_date', 'purchase_price', 'purchase_site', 'sell_date', 'sell_price', 'sell_site', 'fee', 'profit', 'deal_complete', 'time_stamp')
    list_filter = ('deal_complete', 'user', 'purchase_site', 'sell_site')
    search_fields = ('user__name', 'item_listing__item__name')
    ordering = ('-time_stamp',)
