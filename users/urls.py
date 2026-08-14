from django.urls import path, include, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views 

app_name = "users"

urlpatterns = [
    path("signup/", views.signup_page, name="signup"),
    path("login/", views.login_page, name="login"),
    path("logout/", views.log_out, name="logout"),
    path('verify/', views.verify_otp, name='verify_otp'),
    path('2fa/toggle/', views.toggle_2fa, name='toggle_2fa'),
    path('2fa/verify-setup/', views.verify_2fa_setup, name='verify_2fa_setup'),

    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='users/password_reset.html',
        email_template_name='users/password_reset_email.txt',
        success_url=reverse_lazy('users:password_reset_done'),
    ), name='password_reset'),

    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='users/password_reset_done.html',
    ), name='password_reset_done'),

    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='users/password_reset_confirm.html',
        success_url=reverse_lazy('users:password_reset_complete'),
    ), name='password_reset_confirm'),

    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='users/password_reset_complete.html',
    ), name='password_reset_complete'),
]