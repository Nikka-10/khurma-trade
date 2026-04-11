from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Value, Q
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404
from .models import TradeBook, Tag
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


def create_tag(user, form):
    tag = form.save(commit=False)
    tag.user = user
    tag.save()


def delete_tag(user, tag_id=None):
    tag = get_object_or_404(Tag, id=tag_id, user=user)
    tag.delete()


def calc_whole_profit(deals_qs):
    return sum(deal.profit or Decimal('0') for deal in deals_qs)

def get_months(user):
    months_qs = (TradeBook.objects
        .filter(user=user)
        .annotate(month=TruncMonth('purchase_date'))
        .values('month')
        .distinct()
        .order_by('-month'))
    return months_qs


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

    return get_money - spend_money

def import_csv(user, csv_file):
    return ImporterForCsv(user).run(csv_file)

