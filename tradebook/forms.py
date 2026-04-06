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
            self.fields['tags'].queryset = Tag.objects.filter(user=self.user)
        else:
            self.fields['tags'].queryset = Tag.objects.none()


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
        sell_mplace = cleaned_data.get('sell_marketplace')
        sell_custom = cleaned_data.get('sell_marketplace_custom')
        purchase_custom = cleaned_data.get('purchase_marketplace_custom')
        status = cleaned_data.get('status')


        if purchase_date and sell_date and sell_date < purchase_date:
            self.add_error('sell_date', "Sell date cannot be earlier than purchase date.")

        if purchase_price and purchase_price <= 0:
            self.add_error('purchase_price', "Purchase price must be greater than zero.")

        if sell_price and sell_price <= 0:
            self.add_error('sell_price', "Purchase price must be greater than zero.")

        if purchase_date and sell_date:
            if not sell_price: self.add_error('sell price', "you forget sell price")

        if purchase_date and sell_date and purchase_price and sell_price: status='sold'

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

class CreateTagForm(forms.ModelForm):
    class Meta:
        model = Tag

        fields = ['tag',]

        widgets = {
            'tag': forms.TextInput(attrs={'class': 'form-control'})
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_tag(self):
        tag = self.cleaned_data['tag']

        if Tag.objects.filter(tag=tag, user=self.user ).exists():
            raise ValidationError("Tag already exists.")
        return tag



            