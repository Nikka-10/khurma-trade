from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'is_staff', 'is_active', 'date_joined']
    search_fields = ['email']
    ordering = ['email']
