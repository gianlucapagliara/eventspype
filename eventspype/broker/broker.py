import collections
import weakref
from abc import abstractmethod
from collections.abc import Callable
from typing import Any

from eventspype.sub.subscriber import EventSubscriber

# Channel-keyed weak subscription map shared by the broker implementations.
_SubscriberRef = weakref.ReferenceType[EventSubscriber]
_Subscriptions = dict[str, set[_SubscriberRef]]
_PendingRemovals = collections.deque[tuple[str, _SubscriberRef]]


def _discard_and_prune(
    subscriptions: _Subscriptions, channel: str, ref: _SubscriberRef
) -> None:
    """Remove a dead ref from a channel's set and drop the channel when it
    empties.

    The caller must hold the lock protecting ``subscriptions``. This is only
    ever invoked from :func:`_drain_pending`, never directly from a weakref
    finalizer (a finalizer must not take the lock — see
    :func:`_make_removal_finalizer`)."""
    subscribers = subscriptions.get(channel)
    if subscribers is None:
        return
    subscribers.discard(ref)
    if not subscribers:
        del subscriptions[channel]


def _make_removal_finalizer(
    pending: _PendingRemovals, channel: str
) -> Callable[[_SubscriberRef], None]:
    """Build a weakref finalizer that queues ``(channel, ref)`` for removal.

    The finalizer runs synchronously during garbage collection, possibly on a
    thread already holding the broker lock (e.g. inside ``subscribe`` or while
    a dispatch snapshot is being taken). It must therefore never acquire the
    lock or mutate the subscriptions dict — doing so would self-deadlock a
    non-reentrant lock or corrupt an in-progress iteration. It only appends to
    the lock-free ``pending`` deque (``deque.append`` is individually
    thread-safe in CPython — it takes an internal critical section, true on both
    the GIL and the free-threaded build); :func:`_drain_pending` is the sole
    consumer and applies the removal under the lock at the next
    subscribe/unsubscribe/dispatch."""

    def _finalizer(ref: _SubscriberRef) -> None:
        pending.append((channel, ref))

    return _finalizer


def _drain_pending(pending: _PendingRemovals, subscriptions: _Subscriptions) -> None:
    """Apply removals queued by weakref finalizers.

    The caller must hold the lock protecting ``subscriptions``."""
    while pending:
        try:
            channel, ref = pending.popleft()
        except IndexError:  # pragma: no cover - concurrently emptied
            break
        _discard_and_prune(subscriptions, channel, ref)


class MessageBroker:
    """
    Abstract base class for message brokers.

    A message broker is responsible for delivering events from publishers to subscribers.
    The default implementation (LocalBroker) dispatches events in-process, while external
    implementations (e.g. RedisBroker) can route events through external message systems.
    """

    @abstractmethod
    def publish(
        self, channel: str, event: Any, event_tag: int | str, caller: Any
    ) -> None:
        """Publish an event to a channel.

        Args:
            channel: The channel/topic name to publish to.
            event: The event object to publish.
            event_tag: The integer event tag.
            caller: The publisher that triggered the event.
        """
        raise NotImplementedError

    @abstractmethod
    def subscribe(self, channel: str, subscriber: EventSubscriber) -> None:
        """Subscribe to events on a channel.

        Args:
            channel: The channel/topic name to subscribe to.
            subscriber: The subscriber to receive events.
        """
        raise NotImplementedError

    @abstractmethod
    def unsubscribe(self, channel: str, subscriber: EventSubscriber) -> None:
        """Unsubscribe from events on a channel.

        Args:
            channel: The channel/topic name to unsubscribe from.
            subscriber: The subscriber to remove.
        """
        raise NotImplementedError
