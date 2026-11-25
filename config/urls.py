
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include("users.urls")),
    path('trade/', include("tradebook.urls")),
    path("accounts/", include('allauth.urls')),
    path('tracking/', include('tracking.urls')),
    path('stripe/', include('djstripe.urls', namespace='djstripe')),
    path('subscriptions/', include('subscriptions.urls')),
]
