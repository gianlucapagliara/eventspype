from abc import abstractmethod
from typing import Any


class EventSubscriber:
    # Slots keep instances compact; subscribers must support weak references
    # (publishers hold them via weakref). Subclasses that do not define
    # __slots__ get a __dict__ as usual and are unaffected.
    __slots__ = ("__weakref__",)

    def __call__(
        self, arg: Any, current_event_tag: int | str, current_event_caller: Any
    ) -> None:
        self.call(arg, current_event_tag, current_event_caller)

    @abstractmethod
    def call(
        self,
        arg: Any,
        current_event_tag: int | str,
        current_event_caller: Any,
    ) -> None:
        raise NotImplementedError


class OwnedEventSubscriber(EventSubscriber):
    __slots__ = ("_owner",)

    def __init__(self, owner: Any) -> None:
        super().__init__()
        self._owner = owner

    @property
    def owner(self) -> Any:
        return self._owner
