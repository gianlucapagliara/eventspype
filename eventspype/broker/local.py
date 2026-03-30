import logging
import threading
import weakref
from typing import Any

from eventspype.broker.broker import MessageBroker
from eventspype.sub.subscriber import EventSubscriber


def _locked_discard(
    lock: threading.Lock,
    subscribers: set[weakref.ReferenceType[EventSubscriber]],
    ref: weakref.ReferenceType[EventSubscriber],
) -> None:
    """Weakref finalizer callback that removes a dead ref under the lock."""
    with lock:
        subscribers.discard(ref)


class LocalBroker(MessageBroker):
    """
    In-process message broker that dispatches events directly to subscribers.

    This is the default broker and preserves the original eventspype behavior:
    synchronous, in-memory event dispatch using weak references.

    Thread safety: a ``threading.Lock`` protects the subscription sets.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscriptions: dict[str, set[weakref.ReferenceType[EventSubscriber]]] = {}
        self._logger: logging.Logger | None = None

    @property
    def logger(self) -> logging.Logger:
        if self._logger is None:
            self._logger = logging.getLogger(__name__)
        return self._logger

    def publish(
        self, channel: str, event: Any, event_tag: int | str, caller: Any
    ) -> None:
        # Snapshot under lock, iterate outside
        with self._lock:
            refs = self._subscriptions.get(channel)
            if refs is None:
                return
            snapshot = tuple(refs)

        for subscriber_ref in snapshot:
            subscriber = subscriber_ref()
            if subscriber is None:
                continue
            try:
                subscriber(event, event_tag, caller)
            except Exception:
                self.logger.error(
                    f"Unexpected error while processing event on channel {channel}.",
                    exc_info=True,
                )

    def subscribe(self, channel: str, subscriber: EventSubscriber) -> None:
        with self._lock:
            if channel not in self._subscriptions:
                self._subscriptions[channel] = set()
            # Use weakref finalizer callback for O(1) amortized cleanup
            subscribers = self._subscriptions[channel]
            lock = self._lock
            subscriber_ref = weakref.ref(
                subscriber,
                lambda ref, _l=lock, _s=subscribers: _locked_discard(_l, _s, ref),
            )
            subscribers.add(subscriber_ref)

    def unsubscribe(self, channel: str, subscriber: EventSubscriber) -> None:
        with self._lock:
            if channel not in self._subscriptions:
                return
            subscriber_ref = weakref.ref(subscriber)
            self._subscriptions[channel].discard(subscriber_ref)
