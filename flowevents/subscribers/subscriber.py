from abc import abstractmethod
from typing import Any


class EventSubscriber:
    def __call__(
        self, arg: Any, current_event_tag: int, current_event_caller: Any
    ) -> None:
        self.call(arg, current_event_tag, current_event_caller)

    @abstractmethod
    def call(
        self,
        arg: Any,
        current_event_tag: int,
        current_event_caller: Any,
    ) -> None:
        raise NotImplementedError


class OwnedEventSubscriber(EventSubscriber):
    def __init__(self, owner: Any) -> None:
        super().__init__()
        self._owner = owner

    @property
    def owner(self) -> Any:
        return self._owner
