from django.db import models
from items.models import Item, Marketplace
from users.models import User


class TrackedItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE,  related_name='tracked_items')
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    marketplaces = models.ManyToManyField(Marketplace, blank=True)

    alert_min = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    alert_max = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notify_telegram = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'item')
        indexes = [
            models.Index(fields=['user', 'item']),
        ]

    def __str__(self):
        return f'{self.user.email} — {self.item.name_on_market}'
