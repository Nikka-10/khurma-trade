import csv
import io

from django.db import transaction



MAX_FILE_LENGTH = 5 * (1024 * 1024)
MAX_ROWS = 10000
MAX_CELL_LENGTH = 2_000
MAX_REPORTED_ERRORS = 50

DATE_FORMAT = '%Y-%m-%d'

VALID_STATUSES = {'inventory', 'listed', 'sold'}

TRADE_HEADERS = {
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
}

TRADE_REQUIRED = {
    'item',
    'purchase_date',
    'purchase_price',
    'status',
}


EXCHANGE_HEADERS = {
    'exchange_key',
    'exchange_date',
    'marketplace',
    'marketplace_custom',
    'estimated_profit',
    'tags',
    'notes',
    'side',
    'item',
    'quantity',
}

EXCHANGE_REQUIRED = {
    'exchange_key',
    'exchange_date',
    'marketplace',
    'side',
    'item',
}


class CsvFormatError(ValueError):
    """Expected problem with a CSV file or its contents."""


def new_result(kind=None):
    return {
        'kind': kind,
        'created': 0,
        'item_lines': 0,
        'skipped': [],
        'skipped_count': 0,
        'warnings': [],
        'file_error': None,
    }


def add_skipped(result, row_number, errors):
    result['skipped_count'] += 1

    if len(result['skipped']) < MAX_REPORTED_ERRORS:
        result['skipped'].append({
            'row': row_number,
            'errors': [str(error) for error in errors],
        })


def form_errors(form):
    """Convert Django form errors into readable messages."""
    messages = []

    for field, errors in form.errors.items():
        name = (
            'Form'
            if field == '__all__'
            else field.replace('_', ' ').capitalize()
        )

        for error in errors:
            messages.append(f'{name}: {error}')

    return messages


def read_upload(csv_file):

    if not csv_file or not csv_file.name.lower().endswith('.csv'):
        raise CsvFormatError(
            'Please upload a file ending in .csv.'
        )

    try:
        raw = csv_file.read(MAX_FILE_LENGTH + 1)
    except (OSError, ValueError) as exc:
        raise CsvFormatError(
            'Could not read the uploaded file.'
        ) from exc

    if len(raw) > MAX_FILE_LENGTH:
        raise CsvFormatError(
            'CSV exceeds the 5 MiB size limit.'
        )

    if not raw:
        raise CsvFormatError('The CSV file is empty.')

    if b'\x00' in raw:
        raise CsvFormatError(
            'The CSV contains invalid NUL bytes.'
        )

    try:
        content = raw.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise CsvFormatError(
            'Save the CSV as UTF-8 and upload it again.'
        ) from exc

    try:
        reader = csv.DictReader(
            io.StringIO(content, newline=''),
            strict=True,
        )

        if not reader.fieldnames:
            raise CsvFormatError(
                'CSV has no header row.'
            )

        headers = [
            str(header).strip().lower()
            for header in reader.fieldnames
        ]

        if not all(headers) or len(headers) != len(set(headers)):
            raise CsvFormatError(
                'Headers must be non-empty and unique.'
            )

        reader.fieldnames = headers

        if 'exchange_key' in headers or 'side' in headers:

            if (
                'purchase_price' in headers
                or 'purchase_date' in headers
            ):
                raise CsvFormatError(
                    'Ambiguous headers: use a trade OR exchange CSV.'
                )

            kind = 'exchange'
            allowed = EXCHANGE_HEADERS
            required = EXCHANGE_REQUIRED

        elif (
            'purchase_price' in headers
            or 'purchase_date' in headers
        ):
            kind = 'trade'
            allowed = TRADE_HEADERS
            required = TRADE_REQUIRED

        else:
            raise CsvFormatError(
                'Cannot identify CSV type. '
                'Trade files need purchase_date and purchase_price; '
                'exchange files need exchange_key and side.'
            )

        unknown = set(headers) - allowed
        missing = required - set(headers)

        if unknown:
            raise CsvFormatError(
                'Unknown columns: ' + ', '.join(sorted(unknown))
            )

        if missing:
            raise CsvFormatError(
                'Missing required columns: ' + ', '.join(sorted(missing))
            )

        rows = []

        for row in reader:
            if len(rows) >= MAX_ROWS:
                raise CsvFormatError(
                    f'CSV contains more than {MAX_ROWS:,} data rows.'
                )

            if None in row or any(
                value is None for value in row.values()
            ):
                raise CsvFormatError(
                    f'CSV line {reader.line_num}: wrong number of columns.'
                )

            if any(
                len(value) > MAX_CELL_LENGTH
                for value in row.values()
            ):
                raise CsvFormatError(
                    f'CSV line {reader.line_num}: '
                    'a field exceeds 2,000 characters.'
                )

            clean_row = {
                key: value.strip()
                for key, value in row.items()
            }

            rows.append((reader.line_num, clean_row))

    except csv.Error as exc:
        raise CsvFormatError(
            'Invalid CSV syntax. Check quotes and separators.'
        ) from exc

    if not rows:
        raise CsvFormatError(
            'CSV contains headers but no data rows.'
        )

    return kind, rows


def prepare_quantity(raw):
    if raw is None or raw.strip() == '':
        return '1', True

    return raw.strip(), False


def validate_id(raw, label, required=False):

    if raw is None or raw == '':
        if required:
            raise CsvFormatError(
                f'{label} is required (use a database ID).'
            )
        return

    if (
        not raw.isascii()
        or not raw.isdecimal()
        or len(raw) > 19
    ):
        raise CsvFormatError(
            f'{label} must be a valid positive integer ID.'
        )

    if not 1 <= int(raw) <= (2**63 - 1):
        raise CsvFormatError(
            f'{label} is outside the supported ID range.'
        )


def tag_ids(raw):
    if not raw:
        return []

    return [
        part.strip()
        for part in raw.split('|')
    ]


def validate_row_ids(row, fields, required=()):
    for field in fields:
        validate_id(
            row.get(field, ''),
            field,
            required=(field in required),
        )

    for tag_id in tag_ids(row.get('tags', '')):
        validate_id(
            tag_id,
            'tag ID',
            required=True,
        )


class ImporterForCsv:

    def __init__(self, user):
        self.user = user

    def run(self, csv_file):
        try:
            kind, rows = read_upload(csv_file)

        except CsvFormatError as exc:
            result = new_result()
            result['file_error'] = str(exc)
            return result

        if kind == 'trade':
            from .trade_csv import TradeCsvImporter
            importer = TradeCsvImporter(self.user)

        else:
            from .exchange_csv import ExchangeCsvImporter
            importer = ExchangeCsvImporter(self.user)

        with transaction.atomic():
            return importer.run(rows)
