import csv
import io
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
            'file_error': '',
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

        reader = csv.DictReader(io.StringIO(decoded))

        error = self.check_headers(reader.fieldnames)
        if error:
            self.result['file_error'] = error
            return self.result

        self.load_cache() # loading data from db

        for i, row in enumerate(reader, start=2):
            if i > self.MAX_ROWS + 1:
                self.result['file_error'] = f"too many rows, max number: {self.MAX_ROWS}"
                break
            self.process_row(row, row_num=i) # very important thing broza!(here starts everything)

        return self.result


    def check_file(self, csv_file):
        if csv_file.size > self.MAX_FILE_LENGTH:
            return "File is too large, max file size 5mb"
        if not csv_file.name.lower().endswith(".csv"):
            return "File is not a csv"

        return None

    def check_headers(self, fieldnames):
        missing = self.EXPECTED_FIELDS.difference(fieldnames)
        if missing:
            return "The following fields are missing: {}".format(", ".join(missing))
        return None


    def load_cache(self):
        self.items_cache = {
            item.name_on_market.lower(): item
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
        row = {k: v.strip() if isinstance(v, str) else v for k, v in row.items()}

        valid_data, errors = self.validate_row(row)
        if errors:
            print(f"Row {row_num} errors: {errors}")
            self.result['skipped'].append({'row':row_num, 'errors': errors})
            return

        try:
            with transaction.atomic():
                self.create_deal(valid_data)
            self.result['created'] += 1
        except Exception as e:
            self.result['skipped'].append({
                'row': row_num,
                'errors': [f'Unexpected error: {str(e)}']
            })

    def validate_row(self, row):
        errors = []
        valid_data = {}

        item = self.validate_item(
            row.get('item', ''),
            field_name='item',
            errors=errors
        )
        if item:
            valid_data['item'] = item

        purchase_price = self.validate_price(
            row.get('purchase_price'),
            field_name='purchase_price',
            required=True,
            errors=errors
        )
        if purchase_price:
            valid_data['purchase_price'] = purchase_price


        sell_price = self.validate_price(
            row.get('sell_price'),
            field_name='sell_price',
            required=False,
            errors=errors
        )
        if sell_price:
            valid_data['sell_price'] = sell_price

        purchase_date = self.validate_date(
            row.get('purchase_date'),
            field_name='purchase_date',
            required=True,
            errors=errors
        )
        if purchase_date:
            valid_data['purchase_date'] = purchase_date

        sell_date = self.validate_date(
            row.get('sell_date'),
            field_name='sell_date',
            required=False,
            errors=errors
        )
        if sell_date:
            valid_data['sell_date'] = sell_date

        hold_till = self.validate_date(
            row.get('hold_till'),
            field_name='hold_till',
            required=False,
            errors=errors
        )
        if hold_till:
            valid_data['hold_till'] = hold_till

        if purchase_date and sell_date and sell_date < purchase_date:
            errors.append('sell_date cannot be earlier than purchase_date')

        purchase_marketplace, purchase_marketplace_custom = self.validate_marketplace(
            row.get('purchase_marketplace'),
            row.get('purchase_marketplace_custom'),
            field_name='purchase_marketplace',
            required=True,
            errors=errors
        )
        if purchase_marketplace is not None:
            valid_data['purchase_marketplace'] = purchase_marketplace
            valid_data['purchase_marketplace_custom'] = purchase_marketplace_custom or ''

        sell_marketplace, sell_marketplace_custom = self.validate_marketplace(
            row.get('sell_marketplace'),
            row.get('sell_marketplace_custom'),
            field_name='sell_marketplace',
            required=False,
            errors=errors
        )
        if sell_marketplace is not None:
            valid_data['sell_marketplace'] = sell_marketplace
            valid_data['sell_marketplace_custom'] = sell_marketplace_custom or ''

        status = row.get('status', 'inventory').strip()
        if status not in self.VALID_STATUSES:
            errors.append(f'status must be one of: {", ".join(self.VALID_STATUSES)}')
        else:
            valid_data['status'] = status
            if status == 'sold':
                if not sell_price:
                    errors.append('sell_price is required when status is sold')
                if not sell_date:
                    errors.append('sell_date is required when status is sold')


        notes = (row.get('notes') or '').strip()
        if len(notes) > 5000:
            errors.append('notes too long, max 5000 characters')
        else:
            valid_data['notes'] = notes


        tags_raw = row.get('tags', '').strip()
        valid_data['tags'] = [
            t.strip() for t in tags_raw.split(',') if t.strip()
        ] if tags_raw else []

        if errors:
            return None, errors
        return valid_data, None


    def validate_item(self, value, field_name, errors):
        value = (value or "").strip().lower()

        if not value:
            errors.append(f'{field_name} is required')
            return None

        item = self.items_cache.get(value)
        if not item:
            errors.append(f'Item "{value}" not found in database')
            return None

        return item


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
            return marketplace, ''

        return marketplace, custom_name


    def validate_date(self, value, field_name, required, errors):
        if not value:
            if required:
                errors.append(f'{field_name} is required')
            return None

        try:
            return datetime.strptime(value, self.DATE_FORMAT).date()
        except ValueError:
            errors.append(f'{field_name} is not a valid date')
            return None


    def create_deal(self, valid_data):
        tags = valid_data.pop('tags', [])

        trade = TradeBook(user=self.user, **valid_data)
        trade.save()

        self.handle_tags(trade, tags)

    def handle_tags(self, trade, tag_names):
        if not tag_names:
            return

        for name in tag_names:
            key = name.lower()
            if key not in self.tag_cache:
                tag = Tag.objects.create(tag=name, user=self.user)
                self.tag_cache[key] = tag
            trade.tags.add(self.tag_cache[key])
