from collections import defaultdict

from django.http import QueryDict

from tradebook.forms import (
    ExchangeForm,
    ExchangeLineFormSet,
)
from tradebook import services

from .csv_importer import (
    new_result,
    add_skipped,
    form_errors,
    prepare_quantity,
    tag_ids,
)


MAX_LINES_PER_GROUP = 200
MAX_PK = 2**63 - 1

PARENT_FIELDS = (
    'exchange_date',
    'marketplace',
    'marketplace_custom',
    'estimated_profit',
    'tags',
    'notes',
)


def is_safe_id(value):
    if not value:
        return True

    return (
        value.isascii()
        and value.isdecimal()
        and len(value) <= 19
        and 0 < int(value) <= MAX_PK
    )


class ExchangeCsvImporter:

    def __init__(self, user):
        self.user = user

    def run(self, rows):
        result = new_result('exchange')
        default_lines = []

        groups = defaultdict(list)

        for row_number, row in rows:
            key = row.get('exchange_key', '')

            if not key or len(key) > 100:
                add_skipped(
                    result,
                    row_number,
                    ['exchange_key must contain 1–100 characters.'],
                )
                continue

            groups[key].append((row_number, row))

        for key, entries in groups.items():

            errors = []
            first_row_number, first_row = entries[0]

            if len(entries) > MAX_LINES_PER_GROUP:
                add_skipped(
                    result,
                    first_row_number,
                    [f'Exchange {key} exceeds the '
                     f'{MAX_LINES_PER_GROUP}-item limit.'],
                )
                continue

            for row_number, row in entries[1:]:

                for field in PARENT_FIELDS:

                    if row.get(field, '') != first_row.get(field, ''):
                        errors.append(
                            f'CSV line {row_number}: '
                            f'{field} differs from other rows.'
                        )

            marketplace_id = first_row.get('marketplace', '')

            if not is_safe_id(marketplace_id):
                errors.append(
                    'Marketplace must contain a valid database ID.'
                )

            tags = tag_ids(first_row.get('tags', ''))

            if any(not tag or not is_safe_id(tag) for tag in tags):
                errors.append(
                    'Tags must contain valid numeric IDs separated by |.'
                )

            sides = {
                'given': [],
                'received': [],
            }

            assumed_quantities = []

            for row_number, row in entries:

                side = row.get('side', '').lower()

                if side not in sides:
                    errors.append(
                        f'CSV line {row_number}: '
                        'Side must be "given" or "received".'
                    )
                    continue

                item_id = row.get('item', '')

                if item_id and not is_safe_id(item_id):
                    errors.append(
                        f'CSV line {row_number}: '
                        'Invalid item database ID.'
                    )
                    continue

                quantity, defaulted = prepare_quantity(
                    row.get('quantity')
                )

                sides[side].append({
                    'row_number': row_number,
                    'item': item_id,
                    'quantity': quantity,
                })

                if defaulted:
                    assumed_quantities.append(row_number)

            if not sides['given'] or not sides['received']:
                errors.append(
                    'Exchange must contain at least one given '
                    'and one received item.'
                )

            if errors:
                add_skipped(
                    result,
                    first_row_number,
                    [f'Exchange {key}: {error}' for error in errors[:30]],
                )
                continue

            parent_data = QueryDict(mutable=True)

            for field in ExchangeForm.Meta.fields:
                if field != 'tags':
                    parent_data[f'ex-{field}'] = first_row.get(field, '')

            parent_data.setlist('ex-tags', tags)

            form = ExchangeForm(
                parent_data,
                user=self.user,
                prefix='ex',
            )

            formsets = {}

            for side, lines in sides.items():

                data = QueryDict(mutable=True)

                data[f'{side}-TOTAL_FORMS'] = str(len(lines))
                data[f'{side}-INITIAL_FORMS'] = '0'

                for index, line in enumerate(lines):
                    data[f'{side}-{index}-item'] = line['item']
                    data[f'{side}-{index}-quantity'] = line['quantity']

                formsets[side] = ExchangeLineFormSet(
                    data,
                    prefix=side,
                )

            parent_valid = form.is_valid()
            given_valid = formsets['given'].is_valid()
            received_valid = formsets['received'].is_valid()

            if not all((
                parent_valid,
                given_valid,
                received_valid,
            )):
                errors = form_errors(form)

                for side, lines in sides.items():

                    formset = formsets[side]

                    for error in formset.non_form_errors():
                        errors.append(f'{side}: {error}')

                    for index, item_form in enumerate(formset.forms):

                        line_errors = form_errors(item_form)

                        if not line_errors:
                            continue

                        row_number = lines[index]['row_number']

                        for error in line_errors:
                            errors.append(
                                f'CSV line {row_number}: {error}'
                            )

                add_skipped(
                    result,
                    first_row_number,
                    [
                        f'Exchange {key}: {error}'
                        for error in errors[:30]
                    ],
                )
                continue

            services.create_exchange(
                self.user,
                form,
                formsets['given'],
                formsets['received'],
            )

            result['created'] += 1
            result['item_lines'] += len(entries)

            default_lines.extend(assumed_quantities)

        if default_lines:
            example_lines = ', '.join(
                str(number) for number in default_lines[:10]
            )

            result['warnings'].append(
                f'Quantity was missing in '
                f'{len(default_lines)} imported item line(s). '
                f'The system assumed quantity 1. '
                f'Example CSV lines: {example_lines}.'
            )

        return result