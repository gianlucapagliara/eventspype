import logging
from abc import abstractmethod
from collections import defaultdict
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from eventspype.pub.publisher import EventPublisher
from eventspype.sub.subscription import EventSubscription

T = TypeVar("T")


class MultiSubscriber:
    def __init__(self) -> None:
        self._subscribers: dict[EventPublisher, dict[EventSubscription, Any]] = (
            defaultdict(dict)
        )

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
    def subscribers(self) -> dict[EventPublisher, dict[EventSubscription, Any]]:
        return self._subscribers

    # === Subscriptions ===

    def add_subscription(
        self, subscription: EventSubscription, publisher: EventPublisher
    ) -> None:
        if subscription not in self.get_event_definitions().values():
            raise ValueError("Subscription not defined in event definitions")

        if subscription in self._subscribers[publisher]:
            return

        # Save the subscriber to prevent it from being garbage collected
        self._subscribers[publisher][subscription] = subscription(publisher, self)

    def remove_subscription(
        self, subscription: EventSubscription, publisher: EventPublisher
    ) -> None:
        if subscription not in self.get_event_definitions().values():
            raise ValueError("Subscription not defined in event definitions")

        if subscription not in self._subscribers[publisher]:
            return

        subscribers = list(self._subscribers[publisher][subscription])
        for subscriber in subscribers:
            subscription.unsubscribe(publisher, subscriber)
            self._subscribers[publisher][subscription].remove(subscriber)

        del self._subscribers[publisher][subscription]

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
