from django.shortcuts import render, redirect
from items.models import Item, ItemListing, Marketplace
from django.contrib.auth.decorators import login_required
from .models import TradeBook
from users.models import User
from .forms import TradeForm


@login_required
def create_deal(request):
    user = request.user
    if request.method == 'POST':
        form = TradeForm(request.POST, user = user)
        if form.is_valid():
            trade = form.save(commit=False)
            trade.user = user
            trade.save()            
            trade.save_m2m()
            return redirect()   #fill after creating page  
    else:
        form = TradeForm(user = user)  
    return render()     #fill after creating page

