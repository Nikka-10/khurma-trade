from django.db.models import Sum
from django.shortcuts import render, redirect, get_object_or_404
from items.models import Item, ItemListing, Marketplace
from django.contrib.auth.decorators import login_required
from .models import TradeBook, Tag
from users.models import User
from .forms import TradeForm, CreateTagForm
from django.db.models.functions import TruncMonth
from . import services

#@login_required
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
            "is_month_view": is_month_view,# some test stuf for nice front-end, gonna delete later
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
    })

def create_deal(request):
    if request.method == 'POST':
        form = TradeForm(request.POST, user=request.user)
        if form.is_valid():
            services.create_deal(request.user, form)
            return redirect('tradebook:tradebook')
        else:
            tag_form = CreateTagForm(request.POST)
            deals = TradeBook.objects.filter(user=request.user).order_by('-id')
            return render(request, 'tradebook/main.html', {'form': form, 'deals': deals, 'tag_form': tag_form})


def delete_deal(request):
    if request.method == 'POST':

        if "delete_row" in request.POST:
            deal_id = request.POST['delete_row']
            services.delete_deal(request.user, deal_id=deal_id)
        elif 'selected_deals' in request.POST:
            deal_ids = request.POST.getlist('selected_deals')
            services.delete_deal(request.user, deal_ids=deal_ids)

        return redirect('tradebook:tradebook')
    else:
        tag_form = CreateTagForm(request.POST)
        form = TradeForm(request.POST)
        deals = TradeBook.objects.filter(user=request.user).order_by('-id')
        return render(request, 'tradebook/main.html', {'form': form, 'deals': deals, 'tag_form': tag_form})


def create_tag(request):
    if request.method == 'POST':
        tag_form = CreateTagForm(request.POST, user=request.user)
        if tag_form.is_valid():
            services.create_tag(request.user, tag_form)
            return redirect('tradebook:tradebook')
        else:
            form = TradeForm(request.POST)
            deals = TradeBook.objects.filter(user=request.user).order_by('-id')
            return render(request, 'tradebook/main.html', {'form': form, 'deals': deals, 'tag_form': tag_form})


#gonna create later
def uplaod_csv(request):
    if request.method == 'POST':
        csvfile = request.FILES.get('file')
        expected_fields = [
            'item',
            'purchase_date',
            'purchase_price',
            'purchase_marketplace',
            'purchase_marketplace_custom',
            'sell_date',
            'sell_price',
            'sell_marketplace',
            'sell_marketplace_custom',
            'status',
            'hold_till',
            'tags',
            'notes',
        ]
        skipped = {}



