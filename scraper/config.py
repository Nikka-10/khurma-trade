from datetime import timedelta

SCRAPE_INTERVALS = {
    'high':   timedelta(minutes=10),   # items in active price alerts
    'medium': timedelta(hours=24),  # items in tradebooks
    'low':    timedelta(days=7),     # nothing else for now
}

PRIORITY_LEVELS = {
    'high': 3,
    'medium': 2,
    'low': 1,
    'none': 0,
}

BATCH_SIZE = 1000  # how many listings to scrape per task run