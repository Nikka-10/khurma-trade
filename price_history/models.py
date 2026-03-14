from django.db import models
from items.models import ItemListing

class PriceHistory(models.Model):
    item_listing = models.ForeignKey(ItemListing, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    fee = models.DecimalField(max_digits=8, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    time_stamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['item_listing', '-time_stamp']),
            models.Index(fields=['time_stamp']),
        ]