import logging
import weakref
from typing import Any

from eventspype.pub.publication import EventPublication
from eventspype.sub.subscriber import EventSubscriber


class EventPublisher:
    """
    EventPublisher with weak references for a single event type. This avoids the lapsed
    subscriber problem by using weakref finalizer callbacks for automatic cleanup.

    When a subscriber is garbage collected, its weakref callback automatically removes the
    reference from the subscriber set, making cleanup O(1) amortized instead of O(n) per
    publish call.
    """

    def __init__(self, publication: EventPublication) -> None:
        self._publication = publication
        self._subscribers: set[weakref.ReferenceType[EventSubscriber]] = set()
        self._logger: logging.Logger | None = None

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @property
    def logger(self) -> logging.Logger:
        if self._logger is None:
            self._logger = logging.getLogger(__name__)
        return self._logger

    def add_subscriber(self, subscriber: EventSubscriber) -> None:
        """Add a subscriber for this publisher's event."""
        # Create weak reference with a finalizer callback for automatic cleanup
        subscribers = self._subscribers
        subscriber_ref = weakref.ref(
            subscriber, lambda ref: subscribers.discard(ref)
        )
        self._subscribers.add(subscriber_ref)

    def remove_subscriber(self, subscriber: EventSubscriber) -> None:
        """Remove a subscriber."""
        # Create a temporary weak reference for comparison
        subscriber_ref = weakref.ref(subscriber)

        # Remove the subscriber if it exists
        self._subscribers.discard(subscriber_ref)

    def get_subscribers(self) -> list[EventSubscriber]:
        """Get all active subscribers."""
        # Return only the subscribers that are still alive
        return [
            subscriber
            for subscriber in (ref() for ref in self._subscribers)
            if subscriber is not None
        ]

    def publish(self, event: Any, caller: Any | None = None) -> None:
        """Trigger an event, notifying all subscribers with the given message."""
        # Validate event type
        if not isinstance(event, self._publication.event_class):
            raise ValueError(
                f"Invalid event type: expected {self._publication.event_class}, got {type(event)}"
            )

        # Use a tuple snapshot for iteration — cheaper than set.copy() since we
        # only need iteration, not set operations
        for subscriber_ref in tuple(self._subscribers):
            subscriber = subscriber_ref()
            if subscriber is None:
                continue

            try:
                subscriber(event, self._publication.event_tag, caller or self)
            except Exception:
                self._log_exception(event)

    def _log_exception(self, arg: Any) -> None:
        """Log any exceptions that occur during event processing."""
        self.logger.error(
            f"Unexpected error while processing event {self._publication.event_tag}.",
            exc_info=True,
        )
