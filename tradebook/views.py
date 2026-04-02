from django.shortcuts import render, redirect
from items.models import Item, ItemListing, Marketplace
from django.contrib.auth.decorators import login_required
from .models import TradeBook
from users.models import User
from .forms import TradeForm, CreateTagForm
from django.contrib import messages


#@login_required
def tradebook_view(request):
    form = TradeForm(user=request.user)
    tag_form = CreateTagForm()
    deals = TradeBook.objects.filter(user=request.user).order_by('-id')
    user = request.user
    return render(request, 'tradebook/main.html',{
        "form": form,
        "deals": deals,
        'user': user,
        'tag_form': tag_form,
    })

def create_deal(request):
    if request.method == 'POST':
        form = TradeForm(request.POST, user=request.user)
        if form.is_valid():
            trade = form.save(commit=False)
            trade.user = request.user
            trade.save()
            form.save_m2m()
            return redirect('tradebook:tradebook')
        else:
            tag_form = CreateTagForm(request.POST)
            deals = TradeBook.objects.filter(user=request.user).order_by('-id')
            return render(request, 'tradebook/main.html', {'form': form, 'deals': deals, 'tag_form': tag_form})


def delete_deal(request):
    if request.method == 'POST':

        if "delete_row" in request.POST:
            deal_id = request.POST['delete_row']
            tradebook = TradeBook.objects.filter(id=deal_id, user=request.user)
            tradebook.delete()
        elif 'selected_deals' in request.POST:
            ids = request.POST.getlist('selected_deals')
            tradebook = TradeBook.objects.filter(id__in=ids, user=request.user)
            tradebook.delete()

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
            tag = tag_form.save(commit=False)
            tag.user = request.user
            tag.save()
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



