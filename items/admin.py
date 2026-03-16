from django.contrib import admin
from .models import Items, ItemListing

@admin.register(Items)
class ItemsAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'quality', 'source_game', 'image')
    search_fields = ('name', 'source_game')
    list_filter = ('source_game', 'quality')
    ordering = ('name',)
    

@admin.register(ItemListing)
class ItemListingAdmin(admin.ModelAdmin):
    list_display = ('id', 'item', 'site', 'latest_price', 'latest_fee', 'currency', 'last_checked_at', 'price_changed_at')
    search_fields = ('item_name', 'site')
    list_filter = ('site', 'currency')
    ordering = ('item',)