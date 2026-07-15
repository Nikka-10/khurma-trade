import importlib
import pkgutil
from . import notifiers
from .base import BaseNotifier


class NotifierRegistry:
    def __init__(self):
        self._notifiers: dict[str, BaseNotifier] = {}
        self._discover()


    def _discover(self) -> None:
        for _, module_name, _ in pkgutil.iter_modules(notifiers.__path__):
            module = importlib.import_module(f"notification.notifiers.{module_name}")
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type)
                        and issubclass(attr, BaseNotifier)
                        and attr is not BaseNotifier):
                    instance = attr()
                    self._notifiers[instance.notifier_name] = instance

    def get(self, name: str) -> BaseNotifier | None:
        return self._notifiers.get(name)

    def all(self) -> list[BaseNotifier]:
        return list(self._notifiers.values())


registry = NotifierRegistry()

