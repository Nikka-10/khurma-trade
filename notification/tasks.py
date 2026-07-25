from celery import shared_task
from notification.services import check_price_alerts

@shared_task
def check_alerts():
    check_price_alerts()
    return 'Alerts checked'