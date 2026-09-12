from django.urls import path, include
from . import views


app_name = 'subscriptions'

urlpatterns = [
    path('', views.subscription_view, name='plans'),
    path('create-subscription/', views.create_subscription, name='create_subscription'),
    path('payment_success/', views.payment_success, name='payment_success'),
    path('cancel/', views.cancel_subscription, name='cancel'),
    path('redeem/', views.redeem_promo_code, name='redeem'),
    path('webhook/', views.stripe_webhook, name='webhook'),
    path('need-subscription/<str:tier>/', views.need_sub_page, name='need_sub'),
]