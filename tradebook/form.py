from django import forms
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
    
    
    def clean(self):
        cleaned_data = super().clean()
        
        purchase_price = cleaned_data.get('purchase_price')
        sell_price = cleaned_data.get('sell_price')
        
        if purchase_price and purchase_price > 0:
            if not cleaned_data.get('purchase_marketplace') and not cleaned_data.get('purchase_marketplace_custom'):
                self.add_error('purchase_marketplace', "Please select a marketplace or enter a custom name.")

        return cleaned_data
            