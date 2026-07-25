from .models import Item, Marketplace, Game


def search_items(query, game=None, quality=None):
    if len(query) < 2:
        return Item.objects.none()

    qs = Item.objects.filter(name_on_market__icontains=query)

    if game:
        qs = qs.filter(source_game=game)
    if quality:
        qs = qs.filter(quality=quality)

    return qs.values('id', 'name_on_market', 'quality', 'source_game')[:20]

def get_qualities():
    return (Item.objects
        .exclude(quality__isnull=True)
        .exclude(quality='')
        .values_list('quality', flat=True)
        .distinct()
        .order_by('quality'))


def get_marketplaces():
    return Marketplace.objects.all()