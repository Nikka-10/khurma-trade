from django.urls import path, include
from . import views


app_name = 'subscriptions'

urlpatterns = [
    path('', views.subscription_view, name='plans'),
    path('checkout/<str:tier>/<str:period>/', views.checkout_view, name='checkout'),
    path('create-payment-intent/', views.create_subscription_intent, name='create_payment_intent'),
    path('success/', views.payment_success, name='success'),
    path('cancel/', views.cancel_subscription, name='cancel'),
    path('redeem/', views.redeem_promo_code, name='redeem'),
    path('webhook/', views.stripe_webhook, name='webhook'),
    path('need-subscription/<str:tier>/', views.need_sub_page, name='need_sub'),
]