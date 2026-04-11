from django.urls import path
from . import views

app_name = "tradebook"

urlpatterns=[
    path('', views.tradebook_view, name="tradebook"),
    path('create_deal/', views.create_deal, name="create_deal"),
    path('delete_deal', views.delete_deal, name="delete_deal"),
    path('create_tag', views.create_tag, name="create_tag"),
    path('delete_tag', views.delete_tag, name="delete_tag"),
    path('upload_csv', views.upload_csv, name="upload_csv"),
]