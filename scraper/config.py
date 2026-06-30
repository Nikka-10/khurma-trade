from datetime import timedelta

SCRAPE_INTERVALS = {
    'high':   timedelta(minutes=5),   # items in active price alerts
    'medium': timedelta(minutes=30),  # items in tradebooks
    'low':    timedelta(hours=24),     # nothing else for now
}

PRIORITY_LEVELS = {
    'high': 3,
    'medium': 2,
    'low': 1,
    'none': 0,
}

BATCH_SIZE = 100  # how many listings to scrape per task run