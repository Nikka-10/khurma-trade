from django.db import transaction
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Value, Q
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404
from .models import TradeBook, Tag, Exchange, ExchangeItems
from decimal import Decimal
from .importers.import_csv import ImporterForCsv



def get_deals(user, tag_id=None, date=None):
    deals_qs = (TradeBook.objects
                .filter(user=user)
                .select_related('purchase_marketplace', 'sell_marketplace', 'item')
                .prefetch_related('tags')
                .order_by('-id'))

    if tag_id:
        tag = get_object_or_404(Tag, id=tag_id, user=user)
        deals_qs = deals_qs.filter(tags=tag)

    if date:
        year, month = date.split('-')
        deals_qs = deals_qs.filter(
            Q(purchase_date__year=year, purchase_date__month=month) |
            Q(sell_date__year=year, sell_date__month=month)
        )

    return deals_qs

def create_deal(user, form):
    deal = form.save(commit=False)
    deal.user = user
    try:
        deal.save()
    except Exception as e:
        print("SAVE ERROR:", e)
    form.save_m2m()

def delete_deal(user, deal_id=None, deal_ids=None):
    if deal_id:
        TradeBook.objects.get(user=user, id=deal_id).delete()
    elif deal_ids:
        TradeBook.objects.filter(user=user, id__in=deal_ids).delete()


def edit_deal(form):
    deal = form.save(commit=False)
    deal.save()
    form.save_m2m()
    return deal


def create_tag(user, form):
    tag = form.save(commit=False)
    tag.user = user
    tag.save()


def get_tags(user):
    return Tag.objects.filter(user=user)

def delete_tag(user, tag_id=None):
    tag = get_object_or_404(Tag, id=tag_id, user=user)
    tag.delete()

def calc_whole_profit(deals_qs):
    return sum(deal.profit or Decimal('0') for deal in deals_qs)

def get_months(user):
    purchase_months = (TradeBook.objects.filter(user=user, purchase_date__isnull=False)
        .annotate(month=TruncMonth('purchase_date')).values('month').distinct())
    sell_months = (TradeBook.objects.filter(user=user, sell_date__isnull=False)
        .annotate(month=TruncMonth('sell_date')).values('month').distinct())
    exchange_months = (Exchange.objects.filter(user=user)
        .annotate(month=TruncMonth('exchange_date')).values('month').distinct())

    return purchase_months.union(sell_months, exchange_months).order_by('-month')


def get_monthly_profit(user, date):
    if not date:
        return Decimal('0.00')

    year, month = date.split('-')
    trades = TradeBook.objects.filter(user=user)

    spend_money = (
        trades
        .filter(purchase_date__year=year, purchase_date__month=month)
        .aggregate(total=Sum('purchase_price'))
    )['total'] or Decimal('0')

    get_money = (
        trades
        .filter(sell_date__year=year, sell_date__month=month, status='sold')
        .annotate(
            net_received=ExpressionWrapper(
                F('sell_price') - (
                    F('sell_price') * F('sell_marketplace__fee_percent') / Value(100)
                ),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )
        .aggregate(total=Sum('net_received'))
    )['total'] or Decimal('0')

    return round(get_money - spend_money, 2)


def get_exchanges(user, date=None, tag_id=None):
    qs = (Exchange.objects
            .filter(user=user)
            .select_related('marketplace')
            .prefetch_related('tags', 'lines__item')
            .order_by('-id', '-exchange_date')
          )

    if tag_id:
        tag = get_object_or_404(Tag, id=tag_id, user=user)
        qs = qs.filter(tags__in=tag)

    if date:
        try:
            year, month = (int(p) for p in date.split('-'))
        except ValueError:
            return qs
        qs = qs.filter(exchange_date__year=year, exchange_date__month=month)

    return qs

def sum_estimated_profit(qs) -> Decimal:
    return qs.aggregate(total=Sum('estimated_profit'))['total'] or Decimal('0')


@transaction.atomic
def create_exchange(user, form, given_formset, received_formset):
    exchange = form.save(commit=False)
    exchange.user = user
    exchange.save()
    form.save_m2m()

    for side, formset in (
            (ExchangeItems.Side.given, given_formset),
            (ExchangeItems.Side.received, received_formset)):
        formset.instance = exchange
        for line in formset.save(commit=False):
            line.side = side
            line.save()

    return exchange


def delete_exchanges(user, exchange_ids):
    ids = [i for i in exchange_ids if str(i).isdigit()]
    Exchange.objects.filter(user=user, id__in=ids).delete()


def import_csv(user, csv_file):
    return ImporterForCsv(user).run(csv_file)

