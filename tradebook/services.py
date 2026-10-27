import logging
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Value, Q
from django.db.models.functions import TruncMonth
from django.db.models.query import QuerySet
from django.shortcuts import get_object_or_404
from .models import TradeBook, Tag, Exchange, ExchangeItems
from decimal import Decimal
from .importers.import_csv import ImporterForCsv
from django.db.models import Prefetch


logger = logging.getLogger(__name__)


def get_deals(user, tag_id=None, date=None) -> QuerySet:
    deals_qs = (TradeBook.objects
                .filter(user=user)
                .select_related('purchase_marketplace', 'sell_marketplace', 'item')
                .prefetch_related('tags')
                .order_by('-id'))
    if tag_id:
        tag = get_object_or_404(Tag, id=tag_id, user=user)
        deals_qs = deals_qs.filter(tags=tag)

    if date:
        try:
            year, month = map(int, date.split('-'))
            if year < 1 or not 1 <= month <= 12:
                raise ValueError
        except (ValueError, AttributeError):
            raise ValidationError("Invalid month filter.")

    return deals_qs

@transaction.atomic
def create_deal(user, form):
    deal = form.save(commit=False)
    deal.user = user
    deal.save()
    form.save_m2m()

    return deal

@transaction.atomic
def delete_deal(user, deal_id=None, deal_ids=None) -> int:
    if deal_id is not None:
        qs = TradeBook.objects.filter(
            user=user,
            pk=deal_id,
        )
    elif deal_ids is not None:
        qs = TradeBook.objects.filter(
            user=user,
            pk__in=deal_ids,
        )
    else:
        return 0

    _, details = qs.delete()

    return details.get(TradeBook._meta.label, 0)


@transaction.atomic
def edit_deal(form):
    deal = form.save(commit=False)
    deal.save()
    form.save_m2m()

    return deal


@transaction.atomic
def create_tag(user, form):
    tag = form.save(commit=False)
    tag.user = user
    tag.save()

    return tag


@transaction.atomic
def get_tags(user):
    return Tag.objects.filter(user=user)

@transaction.atomic
def delete_tag(user, tag_id=None) -> int:
    tag = get_object_or_404(Tag, id=tag_id, user=user)
    _, details = tag.delete()

    return details.get(Tag._meta.label, 0)

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


def get_monthly_profit(user, date) -> Decimal:
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
    qs = (
        Exchange.objects
        .filter(user=user)
        .select_related('marketplace')
        .prefetch_related(
            'tags',
            Prefetch(
                'lines',
                queryset=ExchangeItems.objects
                    .filter(side=ExchangeItems.Side.given)
                    .select_related('item'),
                to_attr='given_lines',
            ),
            Prefetch(
                'lines',
                queryset=ExchangeItems.objects
                    .filter(side=ExchangeItems.Side.received)
                    .select_related('item'),
                to_attr='received_lines',
            ),
        )
        .order_by('-id', '-exchange_date')
    )

    if tag_id:
        tag = get_object_or_404(Tag, id=tag_id, user=user,)
        qs = qs.filter(tags=tag)

    if date:
        year, month = map(int, date.split('-'))
        qs = qs.filter(exchange_date__year=year, exchange_date__month=month,)

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


@transaction.atomic
def delete_exchanges(user, exchange_ids) -> int:
    ids = [
        int(i)
        for i in exchange_ids
        if str(i).isascii() and str(i).isdigit()
    ]

    _, details = (
        Exchange.objects
        .filter(user=user, id__in=ids)
        .delete()
    )

    return details.get(Exchange._meta.label, 0)


@transaction.atomic
def edit_exchange(form) -> Exchange:
    exchange = form.save(commit=False)
    exchange.save()
    form.save_m2m()

    return exchange


def import_csv(user, csv_file):
    return ImporterForCsv(user).run(csv_file)

