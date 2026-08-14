from celery import shared_task

@shared_task
def cleanup_otp_codes():
    from .services import delete_expired_otp_codes
    count = delete_expired_otp_codes()
    return f'Deleted {count} expired OTP codes'