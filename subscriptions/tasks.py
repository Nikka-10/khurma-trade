from celery import shared_task
from .models import ProcessedStripeEvent

@shared_task
def cleanup_processed_events():
    from datetime import timedelta
    from django.utils import timezone
    cutoff = timezone.now() - timedelta(days=7)
    ProcessedStripeEvent.objects.filter(processed_at__lt=cutoff).delete()