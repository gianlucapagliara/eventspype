"""Stress and adversarial tests for the deferred weakref-cleanup machinery.

These harden the fix in commit bf6cfc5 ("defer weakref cleanup to prevent
finalizer lock re-entry deadlock") against high event volume and strange usage
patterns:

* finalizers firing *en masse* while the lock is held (deadlock regression),
* publish-only / read-only workloads reclaiming dead subscribers (the deferral
  must not leak the ``_pending_removals`` deque or stale snapshot entries),
* re-entrant subscribe/unsubscribe from inside ``call()`` during dispatch,
* multi-threaded churn (add / remove / publish / die) hammering the lock,
* resubscribe-after-death not removing the live replacement,
* a subscriber sharing one channel/publisher many times and one whose
  ``call()`` always raises.

The global ``timeout = 30`` in pyproject turns any genuine deadlock into a test
failure rather than a hung suite.
"""

import gc
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Any

from eventspype.broker.local import LocalBroker
from eventspype.pub.publication import EventPublication
from eventspype.pub.publisher import EventPublisher
from eventspype.sub.subscriber import EventSubscriber


class Events(Enum):
    TEST = 1


@dataclass
class SampleEvent:
    value: int


class CountingSubscriber(EventSubscriber):
    def __init__(self) -> None:
        self.count = 0

    def call(self, arg: Any, current_event_tag: int, current_event_caller: Any) -> None:
        self.count += 1


class RaisingSubscriber(EventSubscriber):
    def call(self, arg: Any, current_event_tag: int, current_event_caller: Any) -> None:
        raise RuntimeError("subscriber boom")


def make_publisher() -> EventPublisher:
    return EventPublisher(EventPublication(Events.TEST, SampleEvent))


# --------------------------------------------------------------------------- #
# Deferred-cleanup memory bounds (the regression introduced by deferral)
# --------------------------------------------------------------------------- #


class TestDeferredCleanupBounds:
    def test_publish_only_churn_does_not_grow_unbounded(self) -> None:
        """A publisher used in a publish-only loop while subscribers die must
        reclaim them: the pending-removal deque, the subscriber set, and the
        dispatch snapshot must all stay bounded (not O(total-ever-subscribed)).
        Regression for the deferral leak: publish() now drains opportunistically.
        """
        publisher = make_publisher()
        persistent = CountingSubscriber()
        publisher.add_subscriber(persistent)

        for _ in range(2000):
            transient = CountingSubscriber()
            publisher.add_subscriber(transient)
            del transient
            gc.collect()
            # Publish-only from here on: no further add/remove.
            publisher.publish(SampleEvent(value=1))

        # Only the persistent subscriber survives; everything else reclaimed.
        assert len(publisher._pending_removals) == 0
        assert len(publisher._subscribers) == 1
        assert len(publisher._snapshot) == 1
        assert publisher.get_subscribers() == [persistent]
        assert persistent.count == 2000

    def test_publish_reconciles_after_mass_death(self) -> None:
        """After many subscribers die at once, a single publish reconciles the
        whole backlog (deque, set, and snapshot drop to the live count)."""
        publisher = make_publisher()
        subs = [CountingSubscriber() for _ in range(1000)]
        for s in subs:
            publisher.add_subscriber(s)
        del subs, s  # `s` (the loop var) would otherwise keep one alive
        gc.collect()

        assert len(publisher._pending_removals) == 1000
        publisher.publish(SampleEvent(value=1))
        assert len(publisher._pending_removals) == 0
        assert len(publisher._subscribers) == 0
        assert len(publisher._snapshot) == 0

    def test_get_subscribers_drains(self) -> None:
        """get_subscribers must reclaim dead refs: it may be the only call a
        publish-only publisher ever sees again."""
        publisher = make_publisher()
        subs = [CountingSubscriber() for _ in range(500)]
        for s in subs:
            publisher.add_subscriber(s)
        del subs, s  # `s` (the loop var) would otherwise keep one alive
        gc.collect()

        assert len(publisher._pending_removals) == 500
        assert publisher.get_subscribers() == []
        assert len(publisher._pending_removals) == 0
        assert len(publisher._subscribers) == 0

    def test_steady_state_publish_is_lock_free_fast_path(self) -> None:
        """When nothing is pending, publish must not even touch the lock — the
        opportunistic drain is gated on a deque truthiness check. We assert the
        gate holds the lock open so a publish can run while the lock is held."""
        publisher = make_publisher()
        sub = CountingSubscriber()
        publisher.add_subscriber(sub)
        assert len(publisher._pending_removals) == 0

        # Hold the lock on another thread; a steady-state publish (nothing
        # pending) must complete without blocking on it.
        done = threading.Event()

        def publish_while_locked() -> None:
            publisher.publish(SampleEvent(value=1))
            done.set()

        with publisher._lock:
            t = threading.Thread(target=publish_while_locked, daemon=True)
            t.start()
            assert done.wait(timeout=5.0), (
                "publish blocked on the lock even though nothing was pending"
            )
        assert sub.count == 1


# --------------------------------------------------------------------------- #
# Deadlock regression: finalizers firing en masse under the held lock
# --------------------------------------------------------------------------- #


class TestFinalizerUnderLockStress:
    def test_many_finalizers_under_held_lock_no_deadlock(self) -> None:
        """Hundreds of subscribers dying while the lock is held (the exact
        production freeze) must never deadlock and must not corrupt the set."""
        publisher = make_publisher()
        holders = [CountingSubscriber() for _ in range(500)]
        for s in holders:
            publisher.add_subscriber(s)
        del s  # don't let the loop var keep one subscriber alive

        finished = threading.Event()

        def kill_under_lock() -> None:
            with publisher._lock:
                holders.clear()  # drop all strong refs -> finalizers fire here
                gc.collect()
            finished.set()

        worker = threading.Thread(target=kill_under_lock, daemon=True)
        worker.start()
        assert finished.wait(timeout=10.0), (
            "mass finalizer fire under the held lock self-deadlocked"
        )

        # Backlog is queued; the next mutation reconciles it cleanly.
        keep = CountingSubscriber()
        publisher.add_subscriber(keep)
        assert publisher.get_subscribers() == [keep]

    def test_finalizer_during_snapshot_rebuild_no_corruption(self) -> None:
        """Repeatedly rebuild the locked snapshot while subscribers die in the
        same window: the finalizer must only enqueue (never mutate the set being
        iterated), so the O(n) tuple() rebuild can never raise 'set changed size
        during iteration'."""
        publisher = make_publisher()
        for _ in range(50):
            batch = [CountingSubscriber() for _ in range(200)]
            for s in batch:
                publisher.add_subscriber(s)  # each add rebuilds the snapshot
            del batch
            gc.collect()  # finalizers fire; must not corrupt anything
            publisher.publish(SampleEvent(value=1))
        # No exception == success; set stays consistent.
        assert isinstance(publisher._snapshot, tuple)


# --------------------------------------------------------------------------- #
# Re-entrant mutation from inside call()
# --------------------------------------------------------------------------- #


class TestReentrantMutation:
    def test_subscribe_from_within_call_is_safe(self) -> None:
        """A subscriber that adds another subscriber from inside its own call()
        must not corrupt the in-flight dispatch (snapshot is an immutable tuple
        captured before the loop); the change takes effect on the next publish.
        """
        publisher = make_publisher()
        added: list[CountingSubscriber] = []

        class SelfAdding(EventSubscriber):
            def call(self, arg: Any, tag: int, caller: Any) -> None:
                if len(added) < 3:
                    new = CountingSubscriber()
                    added.append(new)
                    publisher.add_subscriber(new)

        seed = SelfAdding()
        publisher.add_subscriber(seed)

        publisher.publish(SampleEvent(value=1))  # adds one
        publisher.publish(SampleEvent(value=1))  # adds another, first one counts
        # No deadlock, no "changed size during iteration"; new subscribers exist.
        assert len(added) >= 1
        live = publisher.get_subscribers()
        assert seed in live

    def test_unsubscribe_from_within_call_is_safe(self) -> None:
        """Removing oneself during dispatch must not corrupt the iteration."""
        publisher = make_publisher()

        class SelfRemoving(EventSubscriber):
            def __init__(self) -> None:
                self.count = 0

            def call(self, arg: Any, tag: int, caller: Any) -> None:
                self.count += 1
                publisher.remove_subscriber(self)

        sub = SelfRemoving()
        publisher.add_subscriber(sub)
        publisher.publish(SampleEvent(value=1))
        assert sub.count == 1
        publisher.publish(SampleEvent(value=1))  # already removed
        assert sub.count == 1


# --------------------------------------------------------------------------- #
# Multi-threaded soak
# --------------------------------------------------------------------------- #


class TestConcurrentSoak:
    def test_concurrent_add_remove_publish_die(self) -> None:  # noqa: C901
        """Hammer add/remove/publish from several threads while transient
        subscribers die. Asserts no deadlock (timeout would fail) and that
        internal structures stay bounded afterward."""
        publisher = make_publisher()
        stop = threading.Event()
        errors: list[BaseException] = []

        def adder() -> None:
            while not stop.is_set():
                # The subscriber goes out of scope each iteration -> dies ->
                # its finalizer enqueues a removal.
                publisher.add_subscriber(CountingSubscriber())

        def publisher_thread() -> None:
            while not stop.is_set():
                publisher.publish(SampleEvent(value=1))

        def gc_thread() -> None:
            while not stop.is_set():
                gc.collect()

        def guarded(fn: Any) -> Any:
            def run() -> None:
                try:
                    fn()
                except BaseException as exc:  # pragma: no cover - surfaced below
                    errors.append(exc)

            return run

        workers = [adder, adder, publisher_thread, publisher_thread, gc_thread]
        threads = [threading.Thread(target=guarded(w), daemon=True) for w in workers]
        for t in threads:
            t.start()
        stop_timer = threading.Timer(3.0, stop.set)
        stop_timer.start()
        for t in threads:
            t.join(timeout=15.0)
            assert not t.is_alive(), "a worker thread hung (possible deadlock)"
        stop_timer.cancel()

        assert not errors, f"worker raised: {errors!r}"

        # Drain everything and confirm the structures are coherent and bounded.
        gc.collect()
        publisher.publish(SampleEvent(value=1))
        publisher.get_subscribers()
        # All transient subscribers are gone; deque fully drained.
        assert len(publisher._pending_removals) == 0
        assert len(publisher._subscribers) == len(publisher._snapshot)


# --------------------------------------------------------------------------- #
# Correctness of deferral: resubscribe-after-death, dedup, raising subscriber
# --------------------------------------------------------------------------- #


class TestDeferredCorrectness:
    def test_resubscribe_after_death_keeps_live_subscriber(self) -> None:
        """A dead ref queued for removal must not discard a *different* live
        subscriber added to the same set before the drain runs."""
        publisher = make_publisher()
        dying = CountingSubscriber()
        publisher.add_subscriber(dying)
        del dying
        gc.collect()  # queues a dead ref in _pending_removals

        live = CountingSubscriber()
        publisher.add_subscriber(live)  # drains the dead ref, then adds live
        assert publisher.get_subscribers() == [live]
        publisher.publish(SampleEvent(value=1))
        assert live.count == 1

    def test_same_subscriber_many_times_dedups(self) -> None:
        """Adding the same subscriber repeatedly collapses to one set entry
        (equal weakrefs hash the same); a single remove clears it."""
        publisher = make_publisher()
        sub = CountingSubscriber()
        for _ in range(100):
            publisher.add_subscriber(sub)
        assert len(publisher._subscribers) == 1
        publisher.publish(SampleEvent(value=1))
        assert sub.count == 1
        publisher.remove_subscriber(sub)
        assert publisher.get_subscribers() == []

    def test_raising_subscriber_under_churn(self) -> None:
        """A subscriber whose call() always raises must not break dispatch to
        others; it is caught, logged, and dispatch continues.

        Note: we assert ``good`` keeps receiving rather than that the dead
        ``bad`` subscribers are fully collected -- ``exc_info=True`` logging
        captures tracebacks that hold the raising subscriber's frame (and thus
        the subscriber) alive under pytest's log capture, which would make a
        strict ``== [good]`` assertion flaky. Delivery correctness is the
        invariant that matters here.
        """
        publisher = make_publisher()
        good = CountingSubscriber()
        publisher.add_subscriber(good)
        for _ in range(100):
            bad = RaisingSubscriber()
            publisher.add_subscriber(bad)
            publisher.publish(SampleEvent(value=1))
            del bad
            gc.collect()
        publisher.publish(SampleEvent(value=1))
        assert good.count == 101
        assert good in publisher.get_subscribers()

    def test_subscriber_shared_across_many_publishers(self) -> None:
        """One subscriber on many publishers: each publisher holds an
        independent weakref/finalizer enqueuing to its own deque. Death
        reconciles every publisher independently."""
        publishers = [make_publisher() for _ in range(50)]
        sub = CountingSubscriber()
        for p in publishers:
            p.add_subscriber(sub)
        for p in publishers:
            p.publish(SampleEvent(value=1))
        assert sub.count == 50

        del sub
        gc.collect()
        for p in publishers:
            p.publish(SampleEvent(value=1))  # reconciles each
            assert len(p._pending_removals) == 0
            assert len(p._subscribers) == 0


# --------------------------------------------------------------------------- #
# LocalBroker parity
# --------------------------------------------------------------------------- #


class TestLocalBrokerStress:
    def test_local_broker_mass_finalizer_under_lock(self) -> None:
        broker = LocalBroker()
        holders = [CountingSubscriber() for _ in range(400)]
        for s in holders:
            broker.subscribe("chan", s)
        del s  # don't let the loop var keep one subscriber alive

        finished = threading.Event()

        def kill_under_lock() -> None:
            with broker._lock:
                holders.clear()
                gc.collect()
            finished.set()

        worker = threading.Thread(target=kill_under_lock, daemon=True)
        worker.start()
        assert finished.wait(timeout=10.0), "broker mass finalizer deadlocked"

        # Any subsequent op drains the global pending deque.
        broker.publish("chan", SampleEvent(value=1), 1, None)
        assert "chan" not in broker._subscriptions
        assert len(broker._pending_removals) == 0

    def test_local_broker_publish_only_reclaims(self) -> None:
        broker = LocalBroker()
        keep = CountingSubscriber()
        broker.subscribe("keep", keep)
        for _ in range(500):
            transient = CountingSubscriber()
            broker.subscribe("churn", transient)
            del transient
            gc.collect()
            broker.publish("keep", SampleEvent(value=1), 1, None)
        # publish drains the global deque every call.
        assert len(broker._pending_removals) == 0
        assert "churn" not in broker._subscriptions
        assert keep.count == 500
