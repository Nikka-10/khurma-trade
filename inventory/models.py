from django.db import models
from items.models import Items, ItemListing
from users.models import User

class inventory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    item = models.ForeignKey(Items, on_delete=models.CASCADE)
    item_listing = models.ForeignKey(ItemListing, on_delete=models.CASCADE)
    
    STATUS_CHOICES = [
        ('owned', ('Owned')),
        ('listed',('Listed for Sale')), 
        ('sold',  ('Sold'))
    ] 
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='owned')
    purchase_date = models.DateField()
    purchased_price = models.DecimalField(max_digits=12, decimal_places=2)
    hold_end = models.DateTimeField()
    time_stamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'status']),        
            models.Index(fields=['user', 'item']),          
            models.Index(fields=['status']),               
        ]
    
    
class soled(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    items_listing = models.ForeignKey(ItemListing, on_delete=models.CASCADE)
    sell_date = models.DateField()
    sell_price = models.DecimalField(max_digits=12, decimal_places=2)
    fee = models.DecimalField(max_digits=12, decimal_places=2)
    profit = models.DecimalField(max_digits=12, decimal_places=2)
    time_stamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['items_listing']),
            models.Index(fields=['sell_date']),
        ]
