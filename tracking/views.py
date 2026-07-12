from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from items.models import Item, Marketplace, ItemListing
from .models import TrackedItem
from . import services
from items import services as item_services
from items.services import get_qualities


login_url = '/login'

@login_required(login_url=login_url)
def tracking_render(request,  extra_context=None):

    selected_marketplace_ids = request.GET.getlist('marketplaces')
    marketplaces = Marketplace.objects.exclude(name='custom')

    selected_ids = [int(i) for i in selected_marketplace_ids] if selected_marketplace_ids else list(
        marketplaces.values_list('id', flat=True))

    selected_marketplaces = marketplaces.filter(id__in=selected_ids)

    tracked_qs = services.get_tracked_items(request.user)

    item_ids = [t.item_id for t in tracked_qs]
    all_listings = (ItemListing.objects
                    .filter(item_id__in=item_ids, marketplace_id__in=selected_ids)
                    .select_related('marketplace'))

    listings_by_item = {}
    for listing in all_listings:
        listings_by_item.setdefault(listing.item_id, {})[listing.marketplace_id] = listing

    tracked = []
    for t in tracked_qs:
        item_listings = listings_by_item.get(t.item_id, {})
        t.marketplace_listings = [
            {
                'marketplace': m,
                'listing': item_listings.get(m.id)
            }
            for m in selected_marketplaces
        ]
        tracked.append(t)

    context = {
        'tracked': tracked,
        'marketplaces': marketplaces,
        'selected_marketplaces': selected_marketplaces,
        'selected_marketplace_ids': [str(i) for i in selected_ids],
        'qualities': get_qualities(),
    }

    if extra_context:
        context.update(extra_context)

    return render(request, 'tracking/index.html', context)


@login_required(login_url=login_url)
def search_items(request):
    query = request.GET.get('q', '').strip()
    game = request.GET.get('game', '').strip()
    quality = request.GET.get('quality', '').strip()

    items = item_services.search_items(
        query,
        game=game or None,
        quality=quality or None
    )

    return render(request, 'items/partials/item_results.html', {'items': items})


@login_required(login_url=login_url)
def item_prices(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    marketplaces = Marketplace.objects.exclude(name='custom')
    selected_marketplace_ids = request.GET.getlist('marketplaces')

    selected_ids = [int(i) for i in selected_marketplace_ids] if selected_marketplace_ids else None
    listings = services.item_prices(item, selected_marketplace_ids=selected_ids)

    is_tracked = TrackedItem.objects.filter(user=request.user, item=item).exists()

    return render(request, 'tracking/partials/item_prices.html', {
        'item': item,
        'listings': listings,
        'marketplaces': marketplaces,
        'selected_marketplace_ids': selected_marketplace_ids,
        'is_tracked': is_tracked,
    })


@login_required(login_url=login_url)
def track_item(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    if request.method == 'POST':

        marketplace_ids = request.POST.get('marketplaces', '')

        if marketplace_ids:
            marketplace_ids = [int(i) for i in marketplace_ids.split(',') if i]

        alert_min = request.POST.get('alert_min') or None
        alert_max = request.POST.get('alert_max') or None

        tracked, created = services.add_tracked_items(request.user, item, alert_min, alert_max)

        if not created:
            tracked.alert_min = alert_min
            tracked.alert_max = alert_max
            tracked.save()

        if marketplace_ids:
            tracked.marketplaces.set(marketplace_ids)

        return redirect('tracking:tracking')
    return redirect('tracking:item_prices', item_id=item_id)



@login_required(login_url=login_url)
def remove_tracking(request, item_id):
    if request.method == 'POST':
       services.remove_tracked_items(request.user, item_id)
    return redirect('tracking:tracking')