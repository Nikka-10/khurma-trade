from django.core.management.base import BaseCommand
from plain.exceptions import ValidationError

from subscriptions.models import PromoCode
from django.utils import timezone
from datetime import timedelta
import secrets
import string



class Command(BaseCommand):
    help = 'Create a promo code'

    def add_arguments(self, parser):
        parser.add_argument('--code', type=str, help='promo code(auto gen if not provided)')
        parser.add_argument('--tier', type=str, required=True, choices=['base', 'advanced'])
        parser.add_argument('--days', type=int, required=True, choices=[7, 30, 90])
        parser.add_argument('--max-uses', type=int, default=1)
        parser.add_argument('--expires-days', type=int, help='Days until code expires')


    def handle(self, *args, **options):
        code = options['code'] or ''.join(
            secrets.choice(string.ascii_uppercase + string.digits)
            for _ in range(8)
        )

        expires_at= None
        if options['expires_days']:
            expires_at = timezone.now() + timedelta(days=options['expires_days'])

        if PromoCode.objects.filter(code=code).exists():
            self.stdout.write(self.style.WARNING(f'Code {code} already exists'))
            return

        promo = PromoCode(
            code=code,
            tier=options['tier'],
            duration_days=options['days'],
            max_uses=options['max_uses'],
            expires_at=expires_at,
        )

        try:
            promo.full_clean()
            promo.save()
            self.stdout.write(self.style.SUCCESS(
                f'Created: {promo.code} | {promo.tier} | {promo.duration_days} days | max uses: {promo.max_uses}'
            ))
        except ValidationError as e:
            self.stdout.write(self.style.ERROR(f'Validation error: {e}'))
