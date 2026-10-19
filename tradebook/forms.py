from django.utils import timezone
from django import forms
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from items.models import Item
from .models import TradeBook, Tag, Exchange, ExchangeItems
from django.forms import inlineformset_factory

class TradeForm(forms.ModelForm):
    class Meta:
        model = TradeBook

        fields = [
            'item',
            'quantity',
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
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'purchase_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'purchase_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'sell_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'sell_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'hold_till': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'tags': forms.CheckboxSelectMultiple(attrs={'class': 'tag-pills'})
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if args and args[0] and args[0].get('item'):
            self.fields['item'].queryset = Item.objects.filter(id=args[0].get('item'))
        elif self.instance and self.instance.pk:
            self.fields['item'].queryset = Item.objects.filter(id=self.instance.item_id)
        else:
            self.fields['item'].queryset = Item.objects.none()

        self.fields['item'].widget = forms.HiddenInput()

        if self.user:
            self.fields['tags'].queryset = Tag.objects.filter(user=self.user)
        else:
            self.fields['tags'].queryset = Tag.objects.none()


    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')

        if quantity is None:
            raise ValidationError("Quantity is required.")
        if quantity <= 0:
            raise ValidationError("Quantity must be greater than zero.")
        if quantity > 100:
            raise ValidationError("Let's be realistic brother XD, Quantity cannot be greater than 100.")
        return quantity

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
        if len(notes) > 100:
            raise ValidationError("Notes are too long (max 100 characters).")
        return notes

    def clean(self):
        cleaned_data = super().clean()

        purchase_price = cleaned_data.get('purchase_price')
        sell_price = cleaned_data.get('sell_price')
        purchase_date = cleaned_data.get('purchase_date')
        sell_date = cleaned_data.get('sell_date')
        sell_mplace = cleaned_data.get('sell_marketplace')
        sell_custom = cleaned_data.get('sell_marketplace_custom')
        status = cleaned_data.get('status')

        if purchase_date and sell_date and sell_date < purchase_date:
            self.add_error('sell_date', 'Sell date cannot be earlier than purchase date.')

        if purchase_date and sell_date and purchase_price and sell_price:
            status = 'sold'
            cleaned_data['status'] = status

        if status == 'sold':
            if not sell_date:
                self.add_error('sell_date', 'Required when status is sold.')
            if not sell_price:
                self.add_error('sell_price', 'Required when status is sold.')
            if not sell_mplace and not sell_custom:
                self.add_error('sell_marketplace', 'Required when status is sold.')

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


class ExchangeForm(forms.ModelForm):
    class Meta:
        model = Exchange

        fields = [
            'exchange_date',
            'marketplace',
            'marketplace_custom',
            'estimated_profit',
            'tags',
            'notes'
        ]

        widgets = {
            'exchange_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'estimated_profit': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'}),
            'tags': forms.CheckboxSelectMultiple(attrs={'class': 'tag-pills'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

        def __init__(self, *args, **kwargs):
            user = kwargs.pop('user', None)
            super().__init__(*args, **kwargs)

            self.fields['tags'].queryset = (Tag.objects.filter(user=user) if user else Tag.objects.none())

            if not self.is_bound():
                self.fields['exchange_date'].initial = timezone.localdate


        def clean_notes(self):
            notes = self.cleaned_data('notes', '').stripe()
            if len(notes) > 100:
                raise ValidationError("Notes are too long (max 100 characters).")


        def clean(self):
            cleaned_data = super().clean()
            return cleaned_data


class ExchangeItemForm(forms.ModelForm):
    class Meta:
        model = ExchangeItems

        fields = ['item', 'quantity',]

        widgets = {
            'item': forms.HiddenInput(attrs={'class': 'item-id'}),
            'quantity': forms.NumberInput(attrs={'min': 1, 'class': 'qty-input'}),
        }

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            if self.is_bound:
                raw = self.data.get(self.add_prefix('item'))
                item = Item.objects.filter(pk=raw).first() if raw and str(raw).isdigit() else None
            elif self.instance.pk:
                item = self.instance.item
            else:
                item = None
            self.fields['item'].queryset = (
                Item.objects.filter(pk=item.pk) if item else Item.objects.none()
            )
            self.item_label = item.name_on_market if item else ''


        def clean_quantity(self):
            quantity = self.cleaned_data('quantity', '').stripe()
            if quantity is None:
                raise ValidationError("Quantity is required.")
            if quantity <= 0:
                raise ValidationError("Quantity must be greater than zero.")
            if quantity > 100:
                raise ValidationError("Let's be realistic brother XD, Quantity cannot be greater than 100.")
            return quantity

ExchangeLineFormSet = inlineformset_factory(
    Exchange, ExchangeItems, form=ExchangeItemForm,
    extra=0, min_num=1, validate_min=True, can_delete=False,
)