import logging
import random
import weakref
from typing import Any

from eventspype.pub.publication import EventPublication
from eventspype.sub.subscriber import EventSubscriber


class EventPublisher:
    """
    EventPublisher with weak references for a single event type. This avoids the lapsed subscriber problem by periodically
    performing GC on dead event subscribers.

    Dead subscriber cleanup is done by calling _remove_dead_subscribers(), which checks whether the subscriber weak references are
    alive or not, and removes the dead ones. Each call to _remove_dead_subscribers() takes O(n).
    """

    ADD_SUBSCRIBER_GC_PROBABILITY = 0.005

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
        # Create weak reference to the subscriber
        subscriber_ref = weakref.ref(subscriber)
        self._subscribers.add(subscriber_ref)

        # Randomly perform garbage collection
        if random.random() < self.ADD_SUBSCRIBER_GC_PROBABILITY:
            self._remove_dead_subscribers()

    def remove_subscriber(self, subscriber: EventSubscriber) -> None:
        """Remove a subscriber."""
        # Create a temporary weak reference for comparison
        subscriber_ref = weakref.ref(subscriber)

        # Remove the subscriber if it exists
        self._subscribers.discard(subscriber_ref)

        # Clean up dead subscribers
        self._remove_dead_subscribers()

    def get_subscribers(self) -> list[EventSubscriber]:
        """Get all active subscribers."""
        self._remove_dead_subscribers()

        # Return only the subscribers that are still alive
        return [
            subscriber
            for subscriber in (ref() for ref in self._subscribers)
            if subscriber is not None
        ]

    def trigger_event(self, message: Any) -> None:
        """Trigger an event, notifying all subscribers with the given message."""
        # Validate event type
        if not isinstance(message, self._publication.event_class):
            raise ValueError(
                f"Invalid event type: expected {self._publication.event_class}, got {type(message)}"
            )

        self._remove_dead_subscribers()

        # Make a copy of the subscribers to avoid modification during iteration
        subscribers = self._subscribers.copy()

        for subscriber_ref in subscribers:
            subscriber = subscriber_ref()
            if subscriber is None:
                continue

            try:
                subscriber(message, self._publication.event_tag, self)
            except Exception:
                self._log_exception(message)

    def _remove_dead_subscribers(self) -> None:
        """Remove any dead subscribers."""
        # Remove any dead references
        self._subscribers = {ref for ref in self._subscribers if ref() is not None}

    def _log_exception(self, arg: Any) -> None:
        """Log any exceptions that occur during event processing."""
        self.logger.error(
            f"Unexpected error while processing event {self._publication.event_tag}.",
            exc_info=True,
        )
