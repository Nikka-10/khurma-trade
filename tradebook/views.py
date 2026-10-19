from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import TradeBook, Tag
from .forms import TradeForm, CreateTagForm
from . import services
from items import services as item_services
from subscriptions.decorators import need_base_access, need_advanced_access


login_url = '/login'

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

    is_month_view = bool(date)# some AI stuf for front-end, gonna delete later
    if request.headers.get('HX-Request'):
        return render(request, 'tradebook/partials/deals.html', {
            'deals': deals,
            "whole_profit": whole_profit,
            "monthly_profit": monthly_profit,
            'active_month': date,
            "is_month_view": is_month_view, # some test stuff for nice front-end, gonna delete later, probably
            'marketplaces': item_services.get_marketplaces()
        })

    form = TradeForm(user=request.user)
    tag_form = CreateTagForm()

    return render(request, 'tradebook/main.html', {
        "form": form,
        "deals": deals,
        "tag_form": tag_form,
        "tags": tags,
        "months": months,
        "whole_profit": whole_profit,
        "is_month_view": is_month_view,# some test stuf for nice front-end, gonna delete later
        'marketplaces': item_services.get_marketplaces()
    })


@login_required(login_url=login_url)
@need_base_access
def render_main(request, extra_context=None):
    from items.services import get_qualities
    context = {
        'form': TradeForm(user=request.user),
        'tag_form': CreateTagForm(),
        'deals': services.get_deals(request.user),
        'tags': services.get_tags(request.user),
        'months': services.get_months(request.user),
        'marketplaces': item_services.get_marketplaces(),
        'qualities': get_qualities(),  # ← add
    }
    if extra_context:
        context.update(extra_context)
    return render(request, 'tradebook/main.html', context)


@login_required(login_url=login_url)
@need_base_access
def create_deal(request):
    print(request.POST)
    if request.method == 'POST':
        form = TradeForm(request.POST, user=request.user)
        if form.is_valid():
            services.create_deal(request.user, form)
            return redirect('tradebook:tradebook')
        else:
            print("problme with validatoin")
            print(form.errors)
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
def edit_deal(request, deal_id):
    deal = get_object_or_404(TradeBook, id=deal_id, user=request.user)
    if request.method == 'POST':
        form = TradeForm(request.POST, instance=deal, user=request.user)
        if form.is_valid():
            services.edit_deal(form)
            return redirect('tradebook:tradebook')
        print("problem with validation")
        print(form.errors)
        return render_main(request, {'form': form})


@login_required(login_url=login_url)
@need_base_access
def create_tag(request):
    if request.method == 'POST':
        tag_form = CreateTagForm(request.POST, user=request.user)
        if tag_form.is_valid():
            services.create_tag(request.user, tag_form)
            return redirect('tradebook:tradebook')
        else:
            return render_main(request, {'tag_form': tag_form})


@login_required(login_url=login_url)
@need_base_access
def delete_tag(request):
    if request.method == 'POST':
        services.delete_tag(request.user, request.POST.get('tag'))
        return redirect('tradebook:tradebook')
    else:
       return render_main(request)


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
