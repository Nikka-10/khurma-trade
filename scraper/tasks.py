from celery import shared_task
from scraper.services import recalculate_priorities, scrape_due_listings


@shared_task
def update_prices():
    recalculate_priorities()
    count = scrape_due_listings()
    return f'Updated {count} listings'