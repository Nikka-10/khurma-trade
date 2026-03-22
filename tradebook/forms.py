from django import forms
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from .models import TradeBook, Tag

class TradeForm(forms.ModelForm):
    class Meta:
        model = TradeBook
        
        fields = [
            'item',
            'purchase_date',
            'purchase_price',
            'purchase_marketplace',
            'purchase_marketplace_custom',
            'sell_date',
            'sell_price',
            'sell_marketplace',
            'sell_marketplace_custom',
            'status',
            'hold_till',
            'tags',
            'notes',
        ]
        
        widgets = {
            'purchase_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'purchase_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'sell_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'sell_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'hold_till': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'tags': forms.SelectMultiple(attrs={'class': 'form-control'}),
        }
        
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user:
            self.fields['tags'] = Tag.objects.filter(user = self.user)
        else:
            self.fields['tags'] = Tag.objects.none()
            
    def clean_purchase_price(self):
        price = self.cleaned_data.get('purchase_price')
        if price is None:
            raise ValidationError("Purchase price is required.")
        if price <= 0:
            raise ValidationError("Purchase price must be greater than zero.")
        if price > Decimal('9999999.99'):
            raise ValidationError("Price is unrealistically high. Maximum allowed: 9,999,999.99")
        return price

    def clean_sell_price(self):
        price = self.cleaned_data.get('sell_price')
        if price is None:
            return None
        if price <= 0:
            raise ValidationError("Sell price must be greater than zero (if filled).")
        if price > Decimal('9999999.99'):
            raise ValidationError("Sell price is unrealistically high. Maximum allowed: 9,999,999.99")
        return price
    
    def clean_notes(self):
        notes = self.cleaned_data.get('notes', '').strip()
        if len(notes) > 5000:
            raise ValidationError("Notes are too long (max 5000 characters).")
        return notes
    
    def clean(self):
        cleaned_data = super().clean()
        
        purchase_price = cleaned_data.get('purchase_price')
        sell_price = cleaned_data.get('sell_price')
        purchase_date = cleaned_data.get('purchase_date')
        sell_date = cleaned_data.get('sell_date')
        purchase_mplace = cleaned_data.get('purchase_marketplace')
        purchase_custom = cleaned_data.get('purchase_marketplace_custom')
        
        if purchase_date and sell_date and sell_date < purchase_date:
            self.add_error('sell_date', "Sell date cannot be earlier than purchase date.")
        
        if purchase_price and purchase_price > 0:
            if not cleaned_data.get('purchase_marketplace') and not cleaned_data.get('purchase_marketplace_custom'):
                self.add_error('purchase_marketplace', "Please select a marketplace or enter a custom name.")
                
        status = cleaned_data.get('status')
        if status == 'sold':
            missing = []
            if not sell_date:
                missing.append('sell_date')
            if not sell_price:
                missing.append('sell_price')
            if not purchase_mplace and not purchase_custom:
                missing.append('sell_marketplace')
                
            if missing:
                self.add_error(None, f"When status is 'sold', please fill: {', '.join(missing)}")

        return cleaned_data
            