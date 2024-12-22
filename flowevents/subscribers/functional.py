from collections.abc import Callable
from typing import Any

from .subscriber import EventSubscriber


class FunctionalEventSubscriber(EventSubscriber):
    def __init__(
        self,
        callback: Callable[[Any, int, Any], Any],
    ) -> None:
        super().__init__()
        self._callback = callback

    def call(self, arg: Any, current_event_tag: int, current_event_caller: Any) -> None:
        self._callback(arg, current_event_tag, current_event_caller)
