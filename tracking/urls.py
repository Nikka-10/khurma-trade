from django.urls import path
from . import views

app_name = 'tracking'

urlpatterns = [
    path('', views.tracking_page, name='tracking'),
    path('search/', views.search_items, name='search'),
    path('item/<int:item_id>/', views.item_prices, name='item_prices'),
    path('item/<int:item_id>/track/', views.track_item, name='track_item'),
    path('my/', views.my_tracking, name='my_tracking'),
    path('remove/<int:item_id>/', views.remove_tracking, name='remove_tracking'),
]