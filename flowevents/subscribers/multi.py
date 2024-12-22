import logging
from abc import abstractmethod
from collections import defaultdict
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from ..publishers.publisher import EventPublisher
from .subscriptions import EventSubscription

T = TypeVar("T")


class MultiSubscriber:
    def __init__(self) -> None:
        self._listeners: dict[
            EventPublisher, dict[EventSubscription, Any]
        ] = defaultdict(dict)

    # === Class Methods ===

    @classmethod
    def get_event_definitions(cls) -> dict[str, EventSubscription]:
        result = {}
        for name, value in cls.__dict__.items():
            if isinstance(value, EventSubscription):
                result[name] = value
        return result

    # === Properties ===

    @property
    def listeners(self) -> dict[EventPublisher, dict[EventSubscription, Any]]:
        return self._listeners

    # === Subscriptions ===

    def add_subscription(
        self, subscription: EventSubscription, publisher: EventPublisher
    ) -> None:
        if subscription not in self.get_event_definitions().values():
            raise ValueError("Subscription not defined in event definitions")

        if subscription in self._listeners[publisher]:
            return

        # Save the listener to prevent it from being garbage collected
        self._listeners[publisher][subscription] = subscription(publisher, self)

    def remove_subscription(
        self, subscription: EventSubscription, publisher: EventPublisher
    ) -> None:
        if subscription not in self.get_event_definitions().values():
            raise ValueError("Subscription not defined in event definitions")

        if subscription not in self._listeners[publisher]:
            return

        listeners = list(self._listeners[publisher][subscription])
        for listener in listeners:
            subscription.unsubscribe(publisher, listener)
            self._listeners[publisher][subscription].remove(listener)

        del self._listeners[publisher][subscription]

    # === Decorators ===

    @abstractmethod
    def logger(self) -> logging.Logger:
        raise NotImplementedError

    @staticmethod
    def log_event(
        log_level: int = logging.INFO, log_prefix: str = "Event"
    ) -> Callable[..., Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            @wraps(func)
            def wrapper(self: "MultiSubscriber", event: Any) -> Any:
                self.logger().log(log_level, f"[{log_prefix}] {event}")
                return func(self, event)

            return wrapper

        return decorator
