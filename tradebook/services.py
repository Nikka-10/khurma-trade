import logging
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Value, Q
from django.db.models.functions import TruncMonth
from django.db.models.query import QuerySet
from django.shortcuts import get_object_or_404
from .models import TradeBook, Tag, Exchange, ExchangeItems
from decimal import Decimal
from .importers.csv_importer import ImporterForCsv
from django.db.models import Prefetch
from django.db.models.functions import Coalesce


logger = logging.getLogger(__name__)


def get_deals(
    user,
    tag_id=None,
    date=None,
    date_from=None,
    date_to=None,
    profit_min=None,
    profit_max=None,
    sort='newest',
):
    qs = (TradeBook.objects.filter(user=user).select_related(
            'purchase_marketplace',
            'sell_marketplace',
            'item',
        )
        .prefetch_related('tags')
    )

    if tag_id:
        tag = get_object_or_404(Tag, id=tag_id, user=user)
        qs = qs.filter(tags=tag)

    if date:
        year, month = map(int, date.split('-'))

        qs = qs.filter(
            Q(purchase_date__year=year, purchase_date__month=month,)
            |
            Q(sell_date__year=year, sell_date__month=month,)
        )

    elif date_from or date_to:
        purchase_period = Q()
        sell_period = Q()

        if date_from:
            purchase_period &= Q(purchase_date__gte=date_from)
            sell_period &= Q(sell_date__gte=date_from)

        if date_to:
            purchase_period &= Q(purchase_date__lte=date_to)
            sell_period &= Q(sell_date__lte=date_to)

        qs = qs.filter(purchase_period | sell_period)

    qs = qs.annotate(
        activity_date=Coalesce('sell_date', 'purchase_date')
    )

    if sort == 'oldest':
        qs = qs.order_by('activity_date', 'id')
    else:
        qs = qs.order_by('-activity_date', '-id')

    needs_python_profit = (
        profit_min is not None
        or profit_max is not None
        or sort in ('profit_high', 'profit_low')
    )

    if not needs_python_profit:
        return qs

    deals = list(qs)

    profits = {
        deal.pk: (
            deal.profit if deal.sell_price is not None else None
        )
        for deal in deals
    }

    if profit_min is not None or profit_max is not None:
        deals = [
            deal for deal in deals
            if (
                profits[deal.pk] is not None
                and (
                    profit_min is None
                    or profits[deal.pk] >= profit_min
                )
                and (
                    profit_max is None
                    or profits[deal.pk] <= profit_max
                )
            )
        ]

    if sort == 'profit_high':
        deals.sort(
            key=lambda deal: (
                profits[deal.pk] is None,
                -(profits[deal.pk] or Decimal('0')),
                -deal.pk,
            )
        )

    elif sort == 'profit_low':
        deals.sort(
            key=lambda deal: (
                profits[deal.pk] is None,
                profits[deal.pk] or Decimal('0'),
                -deal.pk,
            )
        )

    return deals

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


def get_exchanges(
    user,
    date=None,
    tag_id=None,
    date_from=None,
    date_to=None,
    profit_min=None,
    profit_max=None,
    sort='newest',
):
    qs = (Exchange.objects.filter(user=user).select_related('marketplace')
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
    )

    if tag_id:
        tag = get_object_or_404(Tag, id=tag_id, user=user)
        qs = qs.filter(tags=tag)

    if date:
        year, month = map(int, date.split('-'))

        qs = qs.filter(
            exchange_date__year=year,
            exchange_date__month=month,
        )

    elif date_from or date_to:
        if date_from:
            qs = qs.filter(exchange_date__gte=date_from)

        if date_to:
            qs = qs.filter(exchange_date__lte=date_to)

    if profit_min is not None:
        qs = qs.filter(estimated_profit__gte=profit_min)

    if profit_max is not None:
        qs = qs.filter(estimated_profit__lte=profit_max)

    if sort == 'oldest':
        return qs.order_by('exchange_date', 'id')

    if sort == 'profit_high':
        return qs.order_by(
            F('estimated_profit').desc(nulls_last=True),
            '-id',
        )

    if sort == 'profit_low':
        return qs.order_by(
            F('estimated_profit').asc(nulls_last=True),
            '-id',
        )

    return qs.order_by('-exchange_date', '-id')

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

