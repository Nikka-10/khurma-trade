from django.core.mail import send_mail
from django.conf import settings


def send_verification_code(to: str, code: str):
    send_mail(
        subject='Your verification code',
        message=f'Your verification code is: {code}\n\nExpires in 10 minutes. Do not share this code.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[to],
        fail_silently=False,
    )


def send_password_reset(to: str, reset_url: str):
    send_mail(
        subject='Password reset request',
        message=f'Click the link to reset your password:\n\n{reset_url}\n\nExpires in 10 minutes. Do not share this code.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[to],
        fail_silently=False,
    )