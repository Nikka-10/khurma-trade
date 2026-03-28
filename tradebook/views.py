from django.shortcuts import render, redirect
from items.models import Item, ItemListing, Marketplace
from django.contrib.auth.decorators import login_required
from .models import TradeBook
from users.models import User
from .forms import TradeForm
from django.contrib import messages


#@login_required
def tradebook_view(request):
    form = TradeForm()
    deals = TradeBook.objects.filter(user=request.user).order_by('-id')
    return render(request, 'tradebook/main.html',{
        "form": form,
        "deals": deals
    })

def create_deal(request):
    if request.method == 'POST':
        form = TradeForm(request.POST)
        if form.is_valid():
            trade = form.save(commit=False)
            trade.user = request.user
            trade.save()
            return redirect('tradebook:tradebook')
        else:
            deals = TradeBook.objects.filter(user=request.user).order_by('-id')
            return render(request, 'tradebook/main.html', {'form': form, 'deals': deals})


def delete_deal(request):
    if request.method == 'POST':

        if "delete_row" in request.POST:
            deal_id = request.POST['delete_row']
            tradebook = TradeBook.objects.filter(id=deal_id)
            tradebook.delete()
        elif 'selected_deals' in request.POST:
            ids = request.POST.getlist('selected_deals')
            tradebook = TradeBook.objects.filter(id__in=ids)
            tradebook.delete()

        return redirect('tradebook:tradebook')
    else:
        form = TradeForm(request.POST)
        deals = TradeBook.objects.filter(user=request.user).order_by('-id')
        return render(request, 'tradebook/main.html', {'form': form, 'deals': deals})





