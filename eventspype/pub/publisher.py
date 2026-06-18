import collections
import logging
import threading
import weakref
from typing import Any

from eventspype.broker.broker import MessageBroker
from eventspype.pub.publication import EventPublication
from eventspype.sub.subscriber import EventSubscriber


class EventPublisher:
    """
    EventPublisher with weak references for a single event type. This avoids the lapsed
    subscriber problem by using weakref finalizer callbacks for automatic cleanup.

    When a subscriber is garbage collected its weakref callback queues the dead
    reference; queued refs are drained from the subscriber set under the lock on
    the next add/remove, keeping cleanup O(1) amortized instead of O(n) per
    publish call.

    Optionally accepts a MessageBroker for external event dispatch (e.g. Redis, RabbitMQ).
    When a broker is provided, events are routed through it instead of being dispatched directly.

    Thread safety: a ``threading.Lock`` protects the subscriber set so that
    ``add_subscriber`` / ``remove_subscriber`` and ``_dispatch_local`` can be
    used concurrently from different threads.

    Weakref finalizers never acquire the lock. A finalizer runs synchronously
    during garbage collection on whatever thread triggered the collection --
    including a thread already inside this object's locked region (e.g. an
    allocation in ``add_subscriber`` triggering GC). Acquiring a non-reentrant
    ``Lock`` there would self-deadlock, and mutating the set could corrupt an
    in-progress iteration. The finalizer therefore only appends the dead ref to
    ``_pending_removals``; the actual removal happens in
    ``_drain_pending_removals`` under the lock.
    """

    # Slots avoid a per-instance __dict__ and speed up attribute access on
    # the publish hot path. Subclasses without __slots__ get a __dict__ as
    # usual and are unaffected.
    __slots__ = (
        "_publication",
        "_broker",
        "_lock",
        "_subscribers",
        "_pending_removals",
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
        # Dead-subscriber refs queued by weakref finalizers, drained under the
        # lock at the next add/remove/publish/get_subscribers. The finalizer must
        # not touch the lock or the set directly (see the class docstring), so it
        # only appends here. ``deque.append``/``popleft`` are individually
        # thread-safe in CPython (the deque takes an internal critical section --
        # true on both the GIL and the free-threaded build), and drain is the
        # sole consumer and runs under the lock, so enqueueing from a finalizer
        # needs no lock of its own.
        self._pending_removals: collections.deque[
            weakref.ReferenceType[EventSubscriber]
        ] = collections.deque()
        # Precomputed snapshot of the subscriber set, rebuilt on add/remove
        # under the lock. publish() reads it without locking (the attribute
        # swap is atomic), avoiding a lock acquisition and an O(n) tuple
        # build per publish. A dead ref left in the snapshot dereferences to
        # None and is skipped on dispatch.
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
        """Set or change the broker. Migrates existing subscribers to the new broker.

        The broker swap and the migration snapshot are taken together under the
        lock so they cannot diverge: an ``add_subscriber`` racing this setter
        either lands fully before the swap (its subscriber is in the snapshot
        and gets migrated) or fully after (it reads the new broker and registers
        there directly). The broker I/O itself runs outside the lock to avoid
        holding it across network calls (and to keep the publisher lock from
        ever nesting a broker lock). Concurrent ``remove_subscriber`` during the
        migration loop remains best-effort, but the broker set deduplicates and
        a subsequent remove reconciles it.
        """
        with self._lock:
            old_broker = self._broker
            self._broker = broker
            if old_broker is None and broker is None:
                return
            # Snapshot the live subscribers atomically with the swap. Drain first
            # so dead refs are not migrated.
            self._drain_pending_removals()
            active_subscribers = [
                s for s in (ref() for ref in self._subscribers) if s is not None
            ]

        for subscriber in active_subscribers:
            if old_broker is not None:
                old_broker.unsubscribe(self._channel, subscriber)
            if broker is not None:
                broker.subscribe(self._channel, subscriber)

    def _drain_pending_removals(self) -> None:
        """Remove dead refs queued by weakref finalizers.

        The caller must hold ``self._lock``. Doing the set mutation here --
        serialized by the lock -- rather than in the finalizer is what makes the
        weakref cleanup deadlock-free: the finalizer may fire on a thread that
        already holds the lock or while the set is being iterated, so it only
        enqueues.
        """
        pending = self._pending_removals
        subscribers = self._subscribers
        while pending:
            try:
                subscribers.discard(pending.popleft())
            except IndexError:  # pragma: no cover - concurrently emptied
                break

    def _reconcile_locked(self) -> None:
        """Drain finalizer-queued dead refs and rebuild the dispatch snapshot.

        The caller must hold ``self._lock``. Used by the read paths
        (``get_subscribers`` / ``_dispatch_local``) so that a publish-only
        workload still reclaims dead subscribers: without this, a publisher that
        is subscribed once and then only published to would never drain
        ``_pending_removals`` (it grows unbounded) and would keep walking dead
        refs in the stale snapshot on every dispatch.
        """
        self._drain_pending_removals()
        self._snapshot = tuple(self._subscribers)

    def add_subscriber(self, subscriber: EventSubscriber) -> None:
        """Add a subscriber for this publisher's event."""
        # The finalizer only enqueues the dead ref (lock-free). It must never
        # acquire self._lock: it can fire during GC on a thread already inside
        # the locked region below, and a non-reentrant Lock would self-deadlock.
        subscriber_ref = weakref.ref(subscriber, self._pending_removals.append)
        with self._lock:
            self._drain_pending_removals()
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
            self._drain_pending_removals()
            self._subscribers.discard(subscriber_ref)
            self._snapshot = tuple(self._subscribers)

        # Unregister from broker if present
        if self._broker is not None:
            self._broker.unsubscribe(self._channel, subscriber)

    def get_subscribers(self) -> list[EventSubscriber]:
        """Get all active subscribers."""
        with self._lock:
            # Reclaim finalizer-queued dead refs: get_subscribers is a read path
            # that may be the only call a publish-only publisher ever sees again.
            self._reconcile_locked()
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
        # Reclaim dead subscribers queued by finalizers since the last mutation.
        # The truthiness check on the deque is lock-free, so a steady-state
        # publisher (nothing pending) stays on the fully lock-free fast path; we
        # only pay a lock acquisition when there is actually something to drain.
        # Without this, a publish-only publisher would never reclaim dead refs:
        # the deque would grow unbounded and dispatch would keep walking dead
        # refs in a stale snapshot forever (O(total-ever-subscribed) per
        # publish). add/remove still drain too, so this is belt-and-suspenders.
        if self._pending_removals:
            with self._lock:
                self._reconcile_locked()
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
