from django.contrib import admin
from .models import TradeBook

@admin.register(TradeBook)
class TradeAdmin(admin.ModelAdmin):
    list_display = ['item', 'user', 'purchase_marketplace', 'purchase_date', 'purchase_price',
                    'sell_marketplace', 'sell_price', 'profit', 'status','hold_till']
    list_filter = ['status', 'purchase_date', 'item__source_game']  
    search_fields = ['item__name_on_market', 'user__email', 'notes']
    readonly_fields = ['profit', 'sell_fee_amount', 'buy_site', 'sell_marketplace']
    
