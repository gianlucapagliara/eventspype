import logging
import weakref
from typing import Any

from eventspype.broker.broker import MessageBroker
from eventspype.sub.subscriber import EventSubscriber


class LocalBroker(MessageBroker):
    """
    In-process message broker that dispatches events directly to subscribers.

    This is the default broker and preserves the original eventspype behavior:
    synchronous, in-memory event dispatch using weak references.
    """

    def __init__(self) -> None:
        self._subscriptions: dict[str, set[weakref.ReferenceType[EventSubscriber]]] = (
            {}
        )
        self._logger: logging.Logger | None = None

    @property
    def logger(self) -> logging.Logger:
        if self._logger is None:
            self._logger = logging.getLogger(__name__)
        return self._logger

    def publish(
        self, channel: str, event: Any, event_tag: int, caller: Any
    ) -> None:
        if channel not in self._subscriptions:
            return

        # Clean dead refs and copy to avoid modification during iteration
        self._remove_dead_subscribers(channel)
        subscribers = self._subscriptions.get(channel, set()).copy()

        for subscriber_ref in subscribers:
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
        if channel not in self._subscriptions:
            self._subscriptions[channel] = set()
        self._subscriptions[channel].add(weakref.ref(subscriber))

    def unsubscribe(self, channel: str, subscriber: EventSubscriber) -> None:
        if channel not in self._subscriptions:
            return
        subscriber_ref = weakref.ref(subscriber)
        self._subscriptions[channel].discard(subscriber_ref)
        self._remove_dead_subscribers(channel)

    def _remove_dead_subscribers(self, channel: str) -> None:
        if channel in self._subscriptions:
            self._subscriptions[channel] = {
                ref for ref in self._subscriptions[channel] if ref() is not None
            }
