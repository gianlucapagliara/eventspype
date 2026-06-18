import collections
import logging
import threading
import weakref
from typing import Any

from eventspype.broker.broker import (
    MessageBroker,
    _drain_pending,
    _make_removal_finalizer,
)
from eventspype.sub.subscriber import EventSubscriber


class LocalBroker(MessageBroker):
    """
    In-process message broker that dispatches events directly to subscribers.

    This is the default broker and preserves the original eventspype behavior:
    synchronous, in-memory event dispatch using weak references.

    Thread safety: a ``threading.Lock`` protects the subscription sets. Weakref
    finalizers never take the lock — they queue the dead ref in
    ``_pending_removals``, which is drained under the lock at the next
    subscribe/unsubscribe/publish (see ``broker._make_removal_finalizer``).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscriptions: dict[str, set[weakref.ReferenceType[EventSubscriber]]] = {}
        # Dead refs queued by weakref finalizers, applied under the lock.
        self._pending_removals: collections.deque[
            tuple[str, weakref.ReferenceType[EventSubscriber]]
        ] = collections.deque()
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
            _drain_pending(self._pending_removals, self._subscriptions)
            refs = self._subscriptions.get(channel)
            if refs is None:
                return
            snapshot = tuple(refs)

        for subscriber_ref in snapshot:
            subscriber = subscriber_ref()
            if subscriber is None:
                continue
            try:
                # Direct .call dispatch skips the __call__ delegation frame
                subscriber.call(event, event_tag, caller)
            except Exception:
                self.logger.error(
                    f"Unexpected error while processing event on channel {channel}.",
                    exc_info=True,
                )

    def subscribe(self, channel: str, subscriber: EventSubscriber) -> None:
        # Build the weakref (and its finalizer) outside the lock; the finalizer
        # only enqueues, never locks.
        subscriber_ref = weakref.ref(
            subscriber, _make_removal_finalizer(self._pending_removals, channel)
        )
        with self._lock:
            _drain_pending(self._pending_removals, self._subscriptions)
            subscribers = self._subscriptions.get(channel)
            if subscribers is None:
                subscribers = self._subscriptions[channel] = set()
            subscribers.add(subscriber_ref)

    def unsubscribe(self, channel: str, subscriber: EventSubscriber) -> None:
        with self._lock:
            _drain_pending(self._pending_removals, self._subscriptions)
            subscribers = self._subscriptions.get(channel)
            if subscribers is None:
                return
            subscribers.discard(weakref.ref(subscriber))
            if not subscribers:
                del self._subscriptions[channel]
