import logging
import weakref
from typing import Any

from eventspype.broker.broker import MessageBroker
from eventspype.pub.publication import EventPublication
from eventspype.sub.subscriber import EventSubscriber


class EventPublisher:
    """
    EventPublisher with weak references for a single event type. This avoids the lapsed
    subscriber problem by using weakref finalizer callbacks for automatic cleanup.

    When a subscriber is garbage collected, its weakref callback automatically removes the
    reference from the subscriber set, making cleanup O(1) amortized instead of O(n) per
    publish call.

    Optionally accepts a MessageBroker for external event dispatch (e.g. Redis, RabbitMQ).
    When a broker is provided, events are routed through it instead of being dispatched directly.
    """

    def __init__(
        self,
        publication: EventPublication,
        broker: MessageBroker | None = None,
    ) -> None:
        self._publication = publication
        self._broker = broker
        self._subscribers: set[weakref.ReferenceType[EventSubscriber]] = set()
        self._logger: logging.Logger | None = None

        # Channel name derived from the publication tag for broker routing
        self._channel = str(publication.event_tag)

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @property
    def logger(self) -> logging.Logger:
        if self._logger is None:
            self._logger = logging.getLogger(__name__)
        return self._logger

    @property
    def broker(self) -> MessageBroker | None:
        return self._broker

    @broker.setter
    def broker(self, broker: MessageBroker | None) -> None:
        """Set or change the broker. Migrates existing subscribers to the new broker."""
        old_broker = self._broker
        self._broker = broker

        # Migrate subscribers from old broker to new broker
        if old_broker is not None or broker is not None:
            active_subscribers = self.get_subscribers()
            for subscriber in active_subscribers:
                if old_broker is not None:
                    old_broker.unsubscribe(self._channel, subscriber)
                if broker is not None:
                    broker.subscribe(self._channel, subscriber)

    def add_subscriber(self, subscriber: EventSubscriber) -> None:
        """Add a subscriber for this publisher's event."""
        # Create weak reference with a finalizer callback for automatic cleanup
        subscribers = self._subscribers
        subscriber_ref = weakref.ref(subscriber, lambda ref: subscribers.discard(ref))
        self._subscribers.add(subscriber_ref)

        # Register with broker if present
        if self._broker is not None:
            self._broker.subscribe(self._channel, subscriber)

    def remove_subscriber(self, subscriber: EventSubscriber) -> None:
        """Remove a subscriber."""
        # Create a temporary weak reference for comparison
        subscriber_ref = weakref.ref(subscriber)

        # Remove the subscriber if it exists
        self._subscribers.discard(subscriber_ref)

        # Unregister from broker if present
        if self._broker is not None:
            self._broker.unsubscribe(self._channel, subscriber)

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

        if self._broker is not None:
            # Delegate dispatch to the broker
            self._broker.publish(
                self._channel, event, self._publication.event_tag, caller or self
            )
        else:
            # Direct in-process dispatch
            self._dispatch_local(event, caller)

    def _dispatch_local(self, event: Any, caller: Any | None = None) -> None:
        """Dispatch event directly to local subscribers."""
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
