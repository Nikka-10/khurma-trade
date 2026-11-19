from decimal import Decimal

from django.db.utils import DatabaseError
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .models import TradeBook, Tag, Exchange
from . import services
from items import services as item_services
from subscriptions.decorators import need_base_access, need_advanced_access
import logging
from .forms import (
    TradeForm,
    CreateTagForm,
    ExchangeForm,
    ExchangeLineFormSet,
    TradebookFilterForm,
)


login_url = '/login'

logger = logging.getLogger(__name__)

MODES = {'trade', 'exchange', 'all'}


def _listing_flags(request):
    mode = request.GET.get('mode', 'all')
    if mode not in MODES:
        mode = 'all'

    return {
        'show_trades': mode in ('trade', 'all'),
        'show_exchanges': mode in ('exchange', 'all'),
    }


def _exchange_listing(request, flags, filters=None):
    if not flags['show_exchanges']:
        return {
            'exchanges': [],
            'exchange_profit': Decimal('0'),
        }

    exchanges = services.get_exchanges(
        request.user,
        tag_id=request.GET.get('tag'),
        **(filters or {}),
    )

    return {
        'exchanges': exchanges,
        'exchange_profit': services.sum_estimated_profit(exchanges),
    }


def _exchange_forms(user):
    return {
        'exchange_form': ExchangeForm(user=user, prefix='ex'),
        'given_formset': ExchangeLineFormSet(prefix='given'),
        'received_formset': ExchangeLineFormSet(prefix='received'),
    }


@login_required(login_url=login_url)
@need_base_access
def tradebook_view(request):
    flags = _listing_flags(request)

    filter_form = TradebookFilterForm(request.GET)
    filter_error = None

    tag_id = request.GET.get('tag')

    if filter_form.is_valid():
        filters = filter_form.cleaned_data

        deals = services.get_deals(
            request.user,
            tag_id=tag_id,
            **filters,
        )

        exchange_ctx = _exchange_listing(
            request,
            flags,
            filters,
        )

        month = filters.get('date')

    else:
        filter_error = '; '.join(
            f'{field.replace("_", " ").capitalize()}: {error}'
            for field, errors in filter_form.errors.items()
            for error in errors
        )

        deals = []
        exchange_ctx = {
            'exchanges': [],
            'exchange_profit': Decimal('0'),
        }
        month = None

    whole_profit = services.calc_whole_profit(deals)

    show_monthly_result = (
        month
        and not tag_id
        and filter_form.is_valid()
        and filters.get('profit_min') is None
        and filters.get('profit_max') is None
    )

    active_month = month if show_monthly_result else None

    monthly_profit = (
        services.get_monthly_profit(request.user, month)
        if active_month
        else Decimal('0')
    )

    context = {
        'deals': deals,
        'whole_profit': whole_profit,
        'monthly_profit': monthly_profit,
        'active_month': active_month,
        'is_month_view': bool(active_month),
        'filter_error': filter_error,
        'marketplaces': item_services.get_marketplaces(),
        **flags,
        **exchange_ctx,
    }

    if request.headers.get('HX-Request'):
        return render(
            request,
            'tradebook/partials/deals.html',
            context,
        )

    context.update({
        'form': TradeForm(user=request.user),
        'exchange': ExchangeForm(user=request.user),
        'tag_form': CreateTagForm(),
        'tags': Tag.objects.filter(user=request.user),
        'months': services.get_months(request.user),
        **_exchange_forms(request.user),
    })

    return render(
        request,
        'tradebook/main.html',
        context,
    )


@login_required(login_url=login_url)
@need_base_access
def render_main(request, extra_context=None):
    from items.services import get_qualities
    flags = _listing_flags(request)

    context = {
            'form': TradeForm(user=request.user),
            'tag_form': CreateTagForm(),
            'deals': services.get_deals(request.user),
            'exchanges': services.get_exchanges(request.user),
            'tags': services.get_tags(request.user),
            'months': services.get_months(request.user),
            'marketplaces': item_services.get_marketplaces(),
            'qualities': get_qualities(),
            **flags,
            **_exchange_listing(request, flags),
            **_exchange_forms(request.user),
        }
    if extra_context:
        context.update(extra_context)
    return render(request, 'tradebook/main.html', context)


@login_required(login_url=login_url)
@need_base_access
@require_POST
def create_deal(request):
    try:
        form = TradeForm(request.POST, user=request.user)
        if form.is_valid():
            services.create_deal(request.user, form)
            return redirect('tradebook:tradebook')
    except DatabaseError:
        logger.exception(
            "Failed to create deal for user_id=%s",
            request.user.pk,
        )
        return redirect('tradebook:tradebook')
    return render_main(request, {'form': form})


@login_required(login_url=login_url)
@need_base_access
def delete_deal(request):
    if request.method == 'POST':

        if "delete_row" in request.POST:
            deal_id = request.POST.get('delete_row')
            services.delete_deal(request.user, deal_id=deal_id)
        elif 'selected_deals' in request.POST:
            deal_ids = request.POST.getlist('selected_deals')
            services.delete_deal(request.user, deal_ids=deal_ids)
        return redirect('tradebook:tradebook')
    else:
        return render_main(request)


@login_required(login_url=login_url)
@need_base_access
@require_POST
def edit_deal(request, deal_id):
    deal = get_object_or_404(TradeBook, id=deal_id, user=request.user)
    try:
        form = TradeForm(request.POST, instance=deal, user=request.user)
        if not form.is_valid():
            return render_main(request, {
                'edit_form': form,
                'editing_deal': deal,
            })
        services.edit_deal(form)
    except DatabaseError:
        logger.exception("Failed to edit deal for user_id=%s",request.user.pk,)
        return redirect('tradebook:tradebook')
    return redirect('tradebook:tradebook')


@login_required(login_url=login_url)
@need_base_access
@require_POST
def create_tag(request):
    try:
        tag_form = CreateTagForm(request.POST, user=request.user,)

        if tag_form.is_valid():
            tag = services.create_tag(request.user, tag_form,)
            return redirect('tradebook:tradebook')

    except DatabaseError:
        logger.exception("Failed to create tag for user_id=%s",request.user.pk,)
        return redirect('tradebook:tradebook')

    return render_main(request, {'tag_form': tag_form})


@login_required(login_url=login_url)
@need_base_access
@require_POST
def delete_tag(request):
    services.delete_tag(request.user, request.POST.get('tag'))
    return redirect('tradebook:tradebook')


@login_required(login_url=login_url)
@need_base_access
@require_POST
def upload_csv(request):
    csv_file = request.FILES.get('csv_file')

    if not csv_file:
        return render_main(request, {
            'result': {
                'file_error': 'Please choose a CSV file.'
            },
        })

    try:
        result = services.import_csv(
            request.user,
            csv_file,
        )

    except DatabaseError:
        logger.exception(
            'CSV import failed for user_id=%s',
            request.user.pk,
        )

        result = {
            'file_error': (
                'A database error occurred. '
                'No records from this upload were saved.'
            ),
        }

    return render_main(request, {
        'result': result,
    })


@login_required(login_url=login_url)
@need_base_access
def search_items(request):
    query = request.GET.get('q', '').strip()
    game = request.GET.get('game', '').strip()
    quality = request.GET.get('quality', '').strip()

    items = item_services.search_items( query, game=game or None, quality=quality or None)

    return render(request, 'items/partials/item_results.html', {'items': items})


@login_required(login_url=login_url)
@need_base_access
@require_POST
def create_exchange(request):
    form = ExchangeForm(request.POST, user=request.user, prefix='ex')
    try:
        given = ExchangeLineFormSet(request.POST, prefix='given')
        received = ExchangeLineFormSet(request.POST, prefix='received')

        results = [form.is_valid(), given.is_valid(), received.is_valid()]
        if all(results):
            services.create_exchange(request.user, form, given, received)
            return redirect('tradebook:tradebook')
    except DatabaseError:
        logger.exception("Failed to create exchange for user_id=%s",request.user.pk,)
        return redirect('tradebook:tradebook')

    return render_main(request, {
        'form': form,
        'given': given,
        'received': received,
        'open_tab': 'exchange',
    })


@login_required(login_url=login_url)
@need_base_access
@require_POST
def delete_exchange(request):
    services.delete_exchanges(request.user, request.POST.getlist('exchange_id'))
    return redirect('tradebook:tradebook')


@login_required(login_url=login_url)
@require_POST
@need_base_access
def edit_exchange(request):
    user = request.user
    exchange_id = request.POST.get('exchange_id')
    exchange = get_object_or_404(Exchange, pk=exchange_id, user=user,)
    try:
        form = ExchangeForm(request.POST, user=user, instance=exchange, prefix='edit_ex')

        if form.is_valid():
            edited = services.edit_exchange(form)
            return redirect('tradebook:tradebook')
    except DatabaseError:
        logger.exception("Failed to edit exchange for user_id=%s",request.user.pk,)
        return redirect('tradebook:tradebook')
    return render_main(request, {
        'exchange_form': form,
        'open_tab': 'exchange',
    })
