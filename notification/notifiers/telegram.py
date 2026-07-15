import requests
import os
from notification.base import BaseNotifier, NotificationMessage


class TelegramNotifier(BaseNotifier):

    @property
    def notifier_name(self) -> str:
        return 'telegram'

    def send(self, message: NotificationMessage) -> bool:
        chat_id = getattr(message.user, 'telegram_chat_id', None)
        if not chat_id:
            return False

        token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not token:
            return False

        text = f"*{message.subject}*\n\n{message.body}"
        resp = requests.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            json={
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'Markdown'
            },
            timeout=10
        )
        return resp.status_code == 200