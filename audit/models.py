from django.db import models

from django.conf import settings
from django.db import models


class ActivityEvent(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    action = models.CharField(
        max_length=64,
        db_index=True,
    )

    target_type = models.CharField(max_length=50)

    target_id = models.CharField(max_length=64)

    details = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        ordering = ['-created_at']
