from django.db import models
from items.models import ItemListing
from users.models import User

class notebook(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    item_listing = models.ForeignKey(ItemListing, on_delete=models.CASCADE)
    purchase_date = models.DateField()
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2)
    purchase_site = models.CharField(max_length=50)
    sell_date = models.DateField()
    sell_price = models.DecimalField(max_digits=12, decimal_places=2)
    sell_site = models.CharField(max_length=50)
    fee = models.DecimalField(max_digits=8, decimal_places=2)
    profit = models.DecimalField(max_digits=12, decimal_places=2)
    deal_complete = models.BooleanField()
    time_stamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'deal_complete']),
            models.Index(fields=['user', '-time_stamp']),
            models.Index(fields=['user', 'item_listing']),
        ]