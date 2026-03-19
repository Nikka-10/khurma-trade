from django.db import models

class Items(models.Model):
    name = models.CharField(max_length=255)
    quality = models.CharField(max_length=50, null=True)
    source_game = models.CharField(max_length=50)
    image = models.ImageField(upload_to='item_images/', null=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['source_game']),
        ]   
    
    def __str__(self):
        return self.name
    
class ItemListing(models.Model):
    item = models.ForeignKey(Items, on_delete=models.CASCADE)
    site = models.CharField(max_length=50)
    latest_price = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    latest_fee = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    currency = models.CharField(max_length=3, default='USD')
    last_checked_at = models.DateTimeField(null=True, blank=True)
    price_changed_at = models.DateTimeField(null=True, blank=True)
    url = models.URLField(max_length=500)
    
    class Meta:
        indexes = [
            models.Index(fields=['item']),    
            models.Index(fields=['latest_price']),
            models.Index(fields=['last_checked_at']),   
            models.Index(fields=['item', 'site']),
        ]
    
 