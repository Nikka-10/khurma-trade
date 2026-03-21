from django.contrib import admin
from .models import Marketplace, Item, ItemListing

@admin.register(Marketplace)
class MarketplaceAdmin(admin.ModelAdmin):
    list_display = ['name', 'fee_percent', 'api_supported']
    search_fields = ['name']
    list_editable = ['fee_percent']


class ItemListingInline(admin.TabularInline):
    model = ItemListing
    extra = 1
    fields = ['marketplace', 'current_price', 'currency', 'url']


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ['name','name_on_market', 'source_game', 'quality', 'usage_count']
    search_fields = ['name_on_market', 'name']
    list_filter = ['source_game']
    inlines = [ItemListingInline]


@admin.register(ItemListing)
class ItemListingAdmin(admin.ModelAdmin):
    list_display = ['item', 'marketplace', 'current_price','net_price', 'last_checked_at', 'price_changed_at']
    list_filter = ['marketplace']
    search_fields = ['item__name_on_market']
    readonly_fields = ['net_price', 'fee_amount', 'last_checked_at']