from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .models import TradeBook, Tag, Exchange
from .forms import TradeForm, CreateTagForm, ExchangeForm, ExchangeLineFormSet
from . import services
from items import services as item_services
from subscriptions.decorators import need_base_access, need_advanced_access


login_url = '/login'

MODES = {'trade', 'exchange', 'all'}


def _listing_flags(request):
    mode = request.GET.get('mode', 'all')
    if mode not in MODES:
        mode = 'all'

    return {
        'show_trades': mode in ('trade', 'all'),
        'show_exchanges': mode in ('exchange', 'all'),
    }


def _exchange_listing(request, flags):
    if not flags['show_exchanges']:
        return {'exchanges': [], 'exchange_profit': 0}
    exchanges = services.get_exchanges(
        request.user,
        tag_id=request.GET.get('tag'),
        date=request.GET.get('date'),
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
    tag_id = request.GET.get('tag')
    date = request.GET.get('date')

    deals = services.get_deals(request.user, tag_id=tag_id, date=date)

    whole_profit = services.calc_whole_profit(deals)
    monthly_profit = services.get_monthly_profit(request.user, date)
    months = services.get_months(request.user)
    tags = Tag.objects.filter(user=request.user)

    flags = _listing_flags(request)
    exchange_ctx = _exchange_listing(request, flags)

    is_month_view = bool(date) # some AI stuf for front-end, gonna delete later
    if request.headers.get('HX-Request'):
        return render(request, 'tradebook/partials/deals.html', {
            'deals': deals,
            "whole_profit": whole_profit,
            "monthly_profit": monthly_profit,
            'active_month': date,
            "is_month_view": is_month_view, # some test stuff for nice front-end, gonna delete later, probably
            'marketplaces': item_services.get_marketplaces(),
            **flags,
            **exchange_ctx,
        })

    form = TradeForm(user=request.user)
    exchange_form = ExchangeForm(user=request.user)
    tag_form = CreateTagForm()

    return render(request, 'tradebook/main.html', {
        "form": form,
        "deals": deals,
        'exchange': exchange_form,
        "tag_form": tag_form,
        "tags": tags,
        "months": months,
        "whole_profit": whole_profit,
        "is_month_view": is_month_view, # some test stuf for nice front-end, gonna delete later
        'marketplaces': item_services.get_marketplaces(),
        **flags,
        **exchange_ctx,
        **_exchange_forms(request.user),
    })


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
    form = TradeForm(request.POST, user=request.user)
    if form.is_valid():
        services.create_deal(request.user, form)
        return redirect('tradebook:tradebook')
    else:
        return render_main(request, extra_context={'form': form})


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
    form = TradeForm(request.POST, instance=deal, user=request.user)
    if form.is_valid():
        services.edit_deal(form)
        return redirect('tradebook:tradebook')
    return render_main(request, {'form': form})


@login_required(login_url=login_url)
@need_base_access
@require_POST
def create_tag(request):
    tag_form = CreateTagForm(request.POST, user=request.user)
    if tag_form.is_valid():
        services.create_tag(request.user, tag_form)
        return redirect('tradebook:tradebook')
    else:
        return render_main(request, {'tag_form': tag_form})


@login_required(login_url=login_url)
@need_base_access
@require_POST
def delete_tag(request):
    services.delete_tag(request.user, request.POST.get('tag'))
    return redirect('tradebook:tradebook')


@login_required(login_url=login_url)
@need_base_access
def upload_csv(request):
    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            return redirect('tradebook:tradebook')
        result = services.import_csv(request.user, csv_file)

        return render_main(request, extra_context={'result':result})
    return redirect('tradebook:tradebook')


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
    given = ExchangeLineFormSet(request.POST, prefix='given')
    received = ExchangeLineFormSet(request.POST, prefix='received')

    results = [form.is_valid(), given.is_valid(), received.is_valid()]
    if all(results):
        services.create_exchange(request.user, form, given, received)
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
    form = ExchangeForm(request.POST, user=user, instance=exchange, prefix='ex')

    if form.is_valid():
        edited = services.edit_exchange(form)
        return redirect('tradebook:tradebook')

    return render_main(request, {
        'exchange_form': form,
        'open_tab': 'exchange',
    })
