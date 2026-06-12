import logging
import threading
import weakref
from typing import Any

from eventspype.broker.broker import MessageBroker
from eventspype.pub.publication import EventPublication
from eventspype.sub.subscriber import EventSubscriber


def _locked_discard(
    lock: threading.Lock,
    subscribers: set[weakref.ReferenceType[EventSubscriber]],
    ref: weakref.ReferenceType[EventSubscriber],
) -> None:
    """Weakref finalizer callback that removes a dead ref under the lock."""
    with lock:
        subscribers.discard(ref)


class EventPublisher:
    """
    EventPublisher with weak references for a single event type. This avoids the lapsed
    subscriber problem by using weakref finalizer callbacks for automatic cleanup.

    When a subscriber is garbage collected, its weakref callback automatically removes the
    reference from the subscriber set, making cleanup O(1) amortized instead of O(n) per
    publish call.

    Optionally accepts a MessageBroker for external event dispatch (e.g. Redis, RabbitMQ).
    When a broker is provided, events are routed through it instead of being dispatched directly.

    Thread safety: a ``threading.Lock`` protects the subscriber set so that
    ``add_subscriber`` / ``remove_subscriber`` and ``_dispatch_local`` can be
    used concurrently from different threads.
    """

    # Slots avoid a per-instance __dict__ and speed up attribute access on
    # the publish hot path. Subclasses without __slots__ get a __dict__ as
    # usual and are unaffected.
    __slots__ = (
        "_publication",
        "_broker",
        "_lock",
        "_subscribers",
        "_snapshot",
        "_logger",
        "_channel",
        "__weakref__",
    )

    def __init__(
        self,
        publication: EventPublication,
        broker: MessageBroker | None = None,
    ) -> None:
        self._publication = publication
        self._broker = broker
        self._lock = threading.Lock()
        self._subscribers: set[weakref.ReferenceType[EventSubscriber]] = set()
        # Precomputed snapshot of the subscriber set, rebuilt on add/remove
        # under the lock. publish() reads it without locking (the attribute
        # swap is atomic), avoiding a lock acquisition and an O(n) tuple
        # build per publish. Finalizers only clean the set: a dead ref left
        # in the snapshot dereferences to None and is skipped on dispatch.
        self._snapshot: tuple[weakref.ReferenceType[EventSubscriber], ...] = ()
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
        lock = self._lock
        subscriber_ref = weakref.ref(
            subscriber, lambda ref: _locked_discard(lock, subscribers, ref)
        )
        with self._lock:
            self._subscribers.add(subscriber_ref)
            self._snapshot = tuple(self._subscribers)

        # Register with broker if present
        if self._broker is not None:
            self._broker.subscribe(self._channel, subscriber)

    def remove_subscriber(self, subscriber: EventSubscriber) -> None:
        """Remove a subscriber."""
        # Create a temporary weak reference for comparison
        subscriber_ref = weakref.ref(subscriber)

        with self._lock:
            self._subscribers.discard(subscriber_ref)
            self._snapshot = tuple(self._subscribers)

        # Unregister from broker if present
        if self._broker is not None:
            self._broker.unsubscribe(self._channel, subscriber)

    def get_subscribers(self) -> list[EventSubscriber]:
        """Get all active subscribers."""
        with self._lock:
            refs = list(self._subscribers)
        return [s for s in (ref() for ref in refs) if s is not None]

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
        # Lock-free read of the precomputed snapshot; see __init__ for the
        # invariants. Loop invariants are hoisted out of the dispatch loop.
        snapshot = self._snapshot
        event_tag = self._publication.event_tag
        source = caller or self

        for subscriber_ref in snapshot:
            subscriber = subscriber_ref()
            if subscriber is None:
                continue

            try:
                # Dispatch to .call directly: EventSubscriber.__call__ is a
                # plain delegation to .call, so this skips one frame per
                # delivery without changing the subscriber contract.
                subscriber.call(event, event_tag, source)
            except Exception:
                self._log_exception(event)

    def _log_exception(self, arg: Any) -> None:
        """Log any exceptions that occur during event processing."""
        self.logger.error(
            f"Unexpected error while processing event {self._publication.event_tag}.",
            exc_info=True,
        )
