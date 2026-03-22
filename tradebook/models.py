from django.db import models
from items.models import Item, Marketplace
from users.models import User
from decimal import Decimal
from django.core.validators import MaxValueValidator, MinValueValidator


class Tag(models.Model):
    name = models.CharField(max_length=255)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    class Meta:
        unique_together = [['name', 'user']]
        indexes = [
            models.Index(fields=['user', 'name']),
        ]
    def __str__(self):
        return self.name
    

class TradeBook(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trades')
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    
    purchase_date = models.DateField(null=True, blank=True)
    purchase_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        validators=[
            MinValueValidator(Decimal('0.01')), 
            MaxValueValidator(Decimal('9999999999.99')),])
    purchase_marketplace = models.ForeignKey(Marketplace, on_delete=models.CASCADE, null=True, related_name="purchase_trades")
    purchase_marketplace_custom = models.CharField(max_length=255, null=True)
    
    sell_date = models.DateField(null=True, blank=True)
    sell_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        validators=[
            MinValueValidator(Decimal('0.01')), 
            MaxValueValidator(Decimal('9999999999.99')),])
    sell_marketplace = models.ForeignKey(Marketplace, on_delete=models.CASCADE, null=True, related_name="sell_trades")
    sell_marketplace_custom = models.CharField(max_length=255, null=True)
    
    status = models.CharField( max_length=20,
        choices=[
            ("inventory", "In Inventory"),
            ("listed", "Listed for Sale"),
            ("sold", "Sold"),   
        ],
        default="inventory"
    )
    hold_till = models.DateField(null=True, blank=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name="trades")
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['user', 'item']),
        ]
    
    def __str__(self):
        return f"{self.item} — {self.user.email}"
      
      
    @property  
    def sell_fee_amount(self) -> Decimal:
        if self.sell_price is None or not self.sell_marketplace:
            return Decimal("0.00")
        return self.sell_price * (self.sell_marketplace.fee_percent / Decimal("100"))
    
    @property  
    def profit(self) -> Decimal:
        if self.sell_price is None:
            return Decimal("0.00")
        return self.sell_price - self.purchase_price - self.sell_fee_amount
    
    @property  
    def profit_percent(self) -> Decimal:
        if self.sell_price is None:
            return Decimal("0.00")
        return (self.profit / self.purchase_price) * 100
    
    @property
    def buy_site(self) -> str:
        return self.purchase_marketplace.name if self.purchase_marketplace else self.purchase_marketplace_custom or "Custom"

    @property
    def sell_site(self) -> str:
        return self.sell_marketplace.name if self.sell_marketplace else self.sell_marketplace_custom or "Custom"
      