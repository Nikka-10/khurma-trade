from django.contrib import admin
from .models import inventory, soled

@admin.register(inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'item', 'item_listing', 'status', 'purchase_date', 'purchased_price', 'hold_end', 'time_stamp')
    list_filter = ('status', 'user')
    search_fields = ('user__name', 'item__name', 'item_listing__item__name')
    ordering = ('-time_stamp',)
    
    
@admin.register(soled)
class SoledAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'items_listing', 'sell_date', 'sell_price', 'fee', 'profit', 'time_stamp')
    list_filter = ('user', 'sell_date')
    search_fields = ('user__name', 'items_listing__item__name')
    ordering = ('-sell_date',)


