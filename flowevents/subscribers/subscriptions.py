from collections.abc import Callable
from enum import Enum
from functools import partial
from typing import Any, TypeVar

from ..publishers.publisher import EventPublisher
from .functional import FunctionalEventSubscriber

T = TypeVar("T")


class EventSubscription:
    def __init__(
        self,
        publisher_class: Any,
        event_tag: Any | list[Any],
        callback: Callable[..., Any],
        callback_with_subscriber: bool = True,
    ) -> None:
        self._publisher_class = publisher_class
        self._event_tag = event_tag
        self._callback = callback
        self._callback_with_subscriber = callback_with_subscriber

    def __call__(
        self,
        publisher: EventPublisher,
        subscriber: Any | None = None,
    ) -> list[FunctionalEventSubscriber]:
        return self.subscribe(publisher, subscriber)

    def __hash__(self) -> int:
        return hash((self.publisher_class, self.event_tag_str, self.callback))

    # === Properties ===

    @property
    def publisher_class(self) -> Any:
        return self._publisher_class

    @property
    def event_tag(self) -> Any:
        return self._event_tag

    @property
    def callback(self) -> Callable[..., Any]:
        return self._callback

    @property
    def callback_with_subscriber(self) -> bool:
        return self._callback_with_subscriber

    @property
    def event_tag_str(self) -> str:
        tags = str(self.event_tag)
        if isinstance(self.event_tag, list):
            tags = ", ".join(sorted([str(tag) for tag in self.event_tag]))
            tags = f"[{tags}]"
        return tags

    # === Subscriptions ===

    def subscribe(
        self, publisher: EventPublisher, subscriber: Any
    ) -> list[FunctionalEventSubscriber]:
        subscribers = []
        tags = self._get_event_tags(self.event_tag)
        for event_tag in tags:
            subscribers.append(self._subscribe(publisher, event_tag, subscriber))
        return subscribers

    def unsubscribe(
        self, publisher: EventPublisher, subscriber: FunctionalEventSubscriber
    ) -> None:
        tags = self._get_event_tags(self.event_tag)
        for event_tag in tags:
            self._unsubscribe(publisher, subscriber, event_tag)

    def _get_event_tags(self, event_tag: Any) -> list[int | Enum]:
        tags = event_tag if isinstance(event_tag, list) else [event_tag]
        return [tag if isinstance(tag, Enum | int) else hash(self) for tag in tags]

    def _subscribe(
        self,
        publisher: EventPublisher,
        event_tag: Any,
        subscriber: Any | None = None,
    ) -> FunctionalEventSubscriber:
        if not isinstance(publisher, self.publisher_class):
            raise ValueError("Publisher type mismatch")

        callback = self.callback
        if self.callback_with_subscriber:
            if subscriber is None:
                raise ValueError("Subscriber is required for callback with subscriber")
            callback = partial(self.callback, subscriber)

        subscriber = FunctionalEventSubscriber(callback)
        publisher.add_subscriber(subscriber)
        return subscriber

    def _unsubscribe(
        self,
        publisher: EventPublisher,
        subscriber: FunctionalEventSubscriber,
        event_tag: Any,
    ) -> None:
        if not isinstance(publisher, self.publisher_class):
            raise ValueError("Publisher type mismatch")
        publisher.remove_subscriber(subscriber)
