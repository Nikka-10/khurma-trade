import csv
import os
from items.models import Item, Marketplace
from tradebook.models import TradeBook, Tag
from decimal import Decimal, InvalidOperation
from django.db import transaction
from datetime import datetime


class ImporterForCsv:
    EXPECTED_FIELDS = {
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
    }

    VALID_STATUSES = {'inventory', 'listed', 'sold'}
    MAX_FILE_LENGTH = 5 * (1024 * 1024)
    MAX_ROWS = 10000
    DATE_FORMAT = '%Y-%m-%d'

    def __init__(self, user,):
        self.user = user
        self.items_cache = {}
        self.marketplace_cache = {}
        self.tag_cache = {}
        self.result = {
            'created': 0,
            'skipped': [],
            'file_error': None,
        }


    def run(self, csv_file):

        error = self.check_file(csv_file)
        if error:
            self.result['file_error'] = error
            return self.result

        try:
            decoded = csv_file.read().decode('utf8')
        except UnicodeDecodeError:
            self.result['file_error'] = "file must be in UTF-8 format"
            return self.result

        reader = csv.DictReader(decoded)

        error = self.check_headers(reader.fieldnames)
        if error:
            self.result['file_error'] = error
            return self.result

        self.load_cache() # loading data from db

        for i, row in enumerate(reader):
            errors = self.check_row(row)
            if errors:
                self.result['file_error'] = errors
            if i > self.MAX_ROWS:
                self.result['file_error'] = "too many rows, max number 10 000"
                break

            self.process_row(row, row_num=i) # very important thing brotha


    def check_file(self, csv_file):
        if csv_file.size > self.MAX_FILE_LENGTH:
            return "File is too large, max file size 5mb"
        if not csv_file.endswith(".csv"):
            return "File is not a csv"
        # try:
        #     csv_file.read().decode('utf8')
        #     csv_file.seek(0)
        # except UnicodeDecodeError:
        #     return "File must be in UTF-8 format"
        return None

    def check_headers(self, fieldnames):
        missing = self.EXPECTED_FIELDS.difference(fieldnames)
        if missing:
            return "The following fields are missing: {}".format(", ".join(missing))
        return None


    def load_cache(self):
        self.items_cache = {
            Item.name.lower(): item
            for item in Item.objects.all()
        }
        self.marketplace_cache = {
            m.name.lower(): m
            for m in Marketplace.objects.all()
        }
        self.tag_cache = {
            tag.tag.lower(): tag
            for tag in Tag.objects.filter(user=self.user)
        }


    def process_row(self, row, row_num):
        errors = self.validate_row(row)

        if errors:
            self.result['skipped'].append({'row':row_num, 'error': errors})
            return
        try:
            with transaction.atomic():
                self.create_deal(row)
            self.result['created'] += 1
        except Exception as e:
            self.result['skipped'].append({
                'row': row_num,
                'errors': [f'Unexpected error: {str(e)}']
            })


    def validate_row(self, row):
        errors = []

        item = self.handle_items(
            row['item'],
            field_name='item',
            required=True, # always required
            errors=errors
        )

        purchase_price = self.validate_price(
             row['purchase_price'],
             'purchase_price',
             required=True,
             errors=errors
        )
        sell_price = self.validate_price(
             row['purchase_price'],
             'purchase_price',
             required=False,
             errors=errors
        )

        purchase_date = self.validate_date(
            row['purchase_date'],
            field_name='purchase_date',
            required=True,
            errors=errors
        )
        sell_date = self.validate_date(
            row['purchase_date'],
            field_name='purchase_date',
            required=True,
            errors=errors
        )
        hold_date = self.validate_date(
            row['hold_date'],
            field_name='hold_date',
            required=False,
            errors=errors
        )
        if purchase_date and sell_date and purchase_date < sell_date:
            errors.append("purchase date is less than sell date")

        marketplace, marketplace_custom = self.validate_marketplace(
            row['marketplace'],
            row['marketplace_custom'],
            field_name='marketplace',
            required=True, # always required
            errors=errors
        )

        return errors


    def handle_items(self, value, field_name, required, errors):
        if not value:
            errors.append(f'{field_name} is required')
        if value not in self.items_cache:
            errors.append(f'Item "{value}" not found in database')
        return value


    def validate_price(self, value, field_name, required, errors):
        if not value:
            if required:
                errors.append(f'{field_name} is required')
            return None
        try:
            price = Decimal(value)
            if price <= 0:
                errors.append(f'{field_name} must be greater than 0')
                return None
            if price > Decimal('9999999.99'):
                errors.append(f'{field_name} is unrealistically high')
                return None
            return price
        except InvalidOperation:
            errors.append(f'{field_name} is not a valid number')
            return None

    def validate_marketplace(self, name, custom_name, field_name, required, errors):
        name = (name or "").strip().lower()
        custom_name = (custom_name or "").strip()

        if required and not name and not custom_name:
            errors.append(f"{field_name} is required")
            return None, None

        if not name and custom_name:
            return self.marketplace_cache.get("custom"), custom_name

        marketplace = self.marketplace_cache.get(name)
        if not marketplace:
            return self.marketplace_cache.get("custom"), name

        if name == "custom":
            if not custom_name:
                errors.append(f"{field_name}_custom is required when using custom")
                return None, None
            return marketplace, custom_name

        if marketplace and custom_name:
            errors.append(f"{field_name}_custom should be empty unless using custom marketplace")

        return marketplace, custom_name


    def validate_date(self, value, field_name, required, errors):
        if not value:
            if required:
                errors.append(f'{field_name} is required')
            return None

        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except ValueError:
            errors.append(f'{field_name} is not a valid date')
            return None


    def create_deal(self, row):
        ...

