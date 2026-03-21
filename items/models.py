from django.db import models
from decimal import Decimal

class Game(models.TextChoices):
    CS2 = "CS2", "counter strike 2"
    RUST = "RUST", "Rust"
    
class Marketplace(models.Model):
    name = models.CharField(max_length=100, unique=True)
    fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.0) 
    url_base = models.URLField(blank=True)
    api_supported = models.BooleanField(default=False)

    def __str__(self):
        return self.name
    

class Item(models.Model):
    name = models.CharField(max_length=255)
    name_on_market = models.CharField(max_length=255, unique=True)
    quality = models.CharField(max_length=50, null=True)
    source_game = models.CharField(max_length=30, choices=Game)
    image = models.ImageField(upload_to='item_images/', null=True)
    
    usage_count = models.PositiveIntegerField(default=0, editable=False)
        
    class Meta:
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['source_game']),
        ]   
    
    def __str__(self):
        return self.name_on_market
    
    
class ItemListing(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    marketplace = models.ForeignKey(Marketplace, on_delete=models.CASCADE)
    current_price = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    currency = models.CharField(max_length=3, default='USD')
    url = models.URLField(max_length=500)

    last_checked_at = models.DateTimeField(null=True, blank=True, auto_now=True)
    price_changed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ('item', 'marketplace')
        indexes = [
            models.Index(fields=['item', 'marketplace']),   
            models.Index(fields=['current_price']),
            models.Index(fields=['last_checked_at']),   
        ]
         
    @property
    def fee_amount(self) -> Decimal:
        return self.current_price * (self.marketplace.fee_percent/100)
    
    @property
    def net_price(self) -> Decimal:
        return self.current_price - self.fee_amount
         

    

    
 