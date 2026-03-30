import logging
from collections import defaultdict
from collections.abc import Callable
from functools import lru_cache, wraps
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
    @lru_cache(maxsize=256)
    def get_event_definitions(cls) -> dict[str, EventSubscription]:
        """Get all event subscriptions defined in the class and its parent classes."""
        result: dict[str, EventSubscription] = {}
        # Traverse the class hierarchy in method resolution order
        for base_class in cls.__mro__:
            for name, value in base_class.__dict__.items():
                if isinstance(value, EventSubscription):
                    # Only add if not already present (child class definitions take precedence)
                    if name in result:
                        continue
                    result[name] = value
        return result

    @classmethod
    @lru_cache(maxsize=256)
    def _valid_subscriptions(cls) -> frozenset[EventSubscription]:
        """Get the set of valid subscriptions for O(1) membership testing."""
        return frozenset(cls.get_event_definitions().values())

    # === Properties ===

    @property
    def subscribers(self) -> dict[EventPublisher, dict[EventSubscription, Any]]:
        return self._subscribers

    # === Subscriptions ===

    def add_subscription(
        self, subscription: EventSubscription, publisher: EventPublisher
    ) -> None:
        if subscription not in self._valid_subscriptions():
            raise ValueError("Subscription not defined in event definitions")

        if subscription in self._subscribers[publisher]:
            return

        # Save the subscriber to prevent it from being garbage collected
        self._subscribers[publisher][subscription] = subscription(publisher, self)

    def remove_subscription(
        self, subscription: EventSubscription, publisher: EventPublisher
    ) -> None:
        if subscription not in self._valid_subscriptions():
            raise ValueError("Subscription not defined in event definitions")

        if subscription not in self._subscribers[publisher]:
            return

        subscribers = list(self._subscribers[publisher][subscription])
        for subscriber in subscribers:
            subscription.unsubscribe(publisher, subscriber)
            self._subscribers[publisher][subscription].remove(subscriber)

        del self._subscribers[publisher][subscription]

    # === Decorators ===

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
