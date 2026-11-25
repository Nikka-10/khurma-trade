
from django.contrib import admin
from .models import ActivityEvent


@admin.register(ActivityEvent)
class ActivityEventAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'actor',
        'action',
        'target_type',
        'target_id',
        'created_at',
    )

    list_filter = (
        'action',
        'target_type',
        'created_at',
    )

    search_fields = (
        'action',
        'target_type',
        'target_id',
        'actor__email',
    )

    readonly_fields = (
        'actor',
        'action',
        'target_type',
        'target_id',
        'details',
        'created_at',
    )

    ordering = ('-created_at',)

    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
