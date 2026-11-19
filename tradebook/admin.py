from django.contrib import admin
from .models import TradeBook, Tag, Exchange, ExchangeItems

@admin.register(TradeBook)
class TradeAdmin(admin.ModelAdmin):
    list_display = ['item', 'user', 'purchase_marketplace', 'purchase_date', 'purchase_price',
                    'sell_marketplace', 'sell_price', 'profit', 'status','hold_till']
    list_filter = ['status', 'purchase_date', 'item__source_game']  
    search_fields = ['item__name_on_market', 'user__email', 'notes']
    readonly_fields = ['profit', 'sell_fee_amount', 'buy_site', 'sell_marketplace']


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['tag', 'user']


class ExchangeItemInline(admin.TabularInline):
    model = ExchangeItems
    extra = 0


@admin.register(Exchange)
class ExchangeAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'user',
        'exchange_date',
        'marketplace',
        'estimated_profit',
        'given_items',
        'received_items',
    ]

    inlines = [ExchangeItemInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('lines__item')

    @admin.display(description='Given Items')
    def given_items(self, obj):
        return ', '.join(
            f'{line.item} x{line.quantity}'
            for line in obj.lines.all()
            if line.side == ExchangeItems.Side.given
        ) or '-'

    @admin.display(description='Received Items')
    def received_items(self, obj):
        return ', '.join(
            f'{line.item} x{line.quantity}'
            for line in obj.lines.all()
            if line.side == ExchangeItems.Side.received
        ) or '-'
