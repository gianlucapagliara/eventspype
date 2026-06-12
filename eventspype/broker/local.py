import logging
import threading
import weakref
from typing import Any

from eventspype.broker.broker import MessageBroker, _locked_discard_and_prune
from eventspype.sub.subscriber import EventSubscriber


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
                # Direct .call dispatch skips the __call__ delegation frame
                subscriber.call(event, event_tag, caller)
            except Exception:
                self.logger.error(
                    f"Unexpected error while processing event on channel {channel}.",
                    exc_info=True,
                )

    def subscribe(self, channel: str, subscriber: EventSubscriber) -> None:
        with self._lock:
            if channel not in self._subscriptions:
                self._subscriptions[channel] = set()
            # Use weakref finalizer callback for O(1) amortized cleanup; the
            # finalizer also prunes the channel entry when it becomes empty
            subscribers = self._subscriptions[channel]
            subscriber_ref = weakref.ref(
                subscriber,
                lambda ref, _l=self._lock, _s=self._subscriptions, _c=channel: (
                    _locked_discard_and_prune(_l, _s, _c, ref)
                ),
            )
            subscribers.add(subscriber_ref)

    def unsubscribe(self, channel: str, subscriber: EventSubscriber) -> None:
        with self._lock:
            subscribers = self._subscriptions.get(channel)
            if subscribers is None:
                return
            subscribers.discard(weakref.ref(subscriber))
            if not subscribers:
                del self._subscriptions[channel]
