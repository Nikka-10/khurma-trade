from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class NotificationMessage:
    subject: str
    body: str
    user: object  

class BaseNotifier(ABC):

    @property
    @abstractmethod
    def notifier_name(self) -> str:
        pass

    @abstractmethod
    def send(self, message: NotificationMessage) -> bool:
        pass