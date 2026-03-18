from django.urls import path
from users import views 

app_name = "users"

urlpatterns = [
    path("auth/", views.auth_page, name="auth")
]