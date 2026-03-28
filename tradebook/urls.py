from django.urls import path
from . import views

app_name = "tradebook"

urlpatterns=[
    path('', views.tradebook_view, name="tradebook"),
    path('create_deal/', views.create_deal, name="create_deal"),
    path('delete_deal', views.delete_deal, name="delete_deal"),
]