from django.urls import path
from . import views 

app_name = "users"

urlpatterns = [
    path("signup/", views.signup_page, name="signup"),
    path("login/", views.login_page, name="login"),
    path("logout/", views.log_out, name="logout"),
]