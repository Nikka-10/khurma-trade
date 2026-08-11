from django.core.mail import send_mail
from django.conf import settings
from notification.base import BaseNotifier, NotificationMessage


class EmailNotifier(BaseNotifier):

    @property
    def notifier_name(self) -> str:
        return 'email'

    def send(self, message: NotificationMessage) -> bool:
        email = getattr(message.user, 'email', None)
        if not email:
            return False
        try:
            send_mail(
                subject=message.subject,
                message=message.body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            return True
        except Exception:
            return False