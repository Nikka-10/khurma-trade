from django.http import QueryDict

from tradebook.forms import TradeForm
from tradebook import services

from .csv_importer import (
    new_result,
    add_skipped,
    form_errors,
    prepare_quantity,
    tag_ids,
)


MAX_PK = 2**63 - 1


def is_safe_id(value):
    if not value:
        return True

    return (
        value.isascii()
        and value.isdecimal()
        and len(value) <= 19
        and 0 < int(value) <= MAX_PK
    )


class TradeCsvImporter:

    def __init__(self, user):
        self.user = user

    def run(self, rows):
        result = new_result('trade')
        default_rows = []

        for row_number, row in rows:
            quantity, defaulted = prepare_quantity(
                row.get('quantity')
            )

            errors = []

            for field in (
                'item',
                'purchase_marketplace',
                'sell_marketplace',
            ):
                if not is_safe_id(row.get(field, '')):
                    errors.append(
                        f'{field}: Invalid database ID.'
                    )

            tags = tag_ids(row.get('tags', ''))

            if any(not is_safe_id(tag) or not tag for tag in tags):
                errors.append(
                    'tags: Use valid numeric tag IDs separated by |.'
                )

            if errors:
                add_skipped(result, row_number, errors)
                continue

            data = QueryDict(mutable=True)

            for field in TradeForm.Meta.fields:
                if field not in ('quantity', 'tags'):
                    data[field] = row.get(field, '')

            data['quantity'] = quantity
            data.setlist('tags', tags)

            form = TradeForm(
                data,
                user=self.user,
            )

            if not form.is_valid():
                add_skipped(
                    result,
                    row_number,
                    form_errors(form),
                )
                continue

            services.create_deal(
                self.user,
                form,
            )

            result['created'] += 1

            if defaulted:
                default_rows.append(row_number)

        if default_rows:
            example_rows = ', '.join(
                str(number) for number in default_rows[:10]
            )

            result['warnings'].append(
                f'Quantity was missing in '
                f'{len(default_rows)} imported trade(s). '
                f'The system assumed quantity 1. '
                f'Example CSV lines: {example_rows}.'
            )

        return result