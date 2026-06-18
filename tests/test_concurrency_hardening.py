"""Concurrency-hardening tests for the follow-up pass after the deferred
weakref-cleanup deadlock fix.

These cover the pre-existing thread-safety gaps that the bf6cfc5 review
surfaced and that were subsequently fixed:

* RedisBroker ``_pubsub`` / ``_listener_thread`` lifecycle is now guarded by a
  dedicated lock (no AttributeError on concurrent close/unsubscribe; no
  duplicate pubsub objects or listener threads under concurrent first-channel
  subscribes),
* MultiPublisher / MultiSubscriber serialize their check-then-act bookkeeping
  (concurrent subscribes to the same new publication can no longer drop a
  subscriber),
* EventPublisher.broker reassignment swaps the broker and snapshots the
  subscribers atomically under the lock.

The global ``timeout = 30`` turns any deadlock into a failure.
"""

import threading
from dataclasses import dataclass
from enum import Enum
from functools import partial
from typing import Any
from unittest.mock import MagicMock

from eventspype.broker.local import LocalBroker
from eventspype.broker.redis import RedisBroker
from eventspype.pub.multipublisher import MultiPublisher
from eventspype.pub.publication import EventPublication
from eventspype.pub.publisher import EventPublisher
from eventspype.sub.multisubscriber import MultiSubscriber
from eventspype.sub.subscriber import EventSubscriber
from eventspype.sub.subscription import EventSubscription


class Events(Enum):
    EVENT_1 = 1
    EVENT_2 = 2


@dataclass
class SampleEvent:
    value: int


class MockSubscriber(EventSubscriber):
    def __init__(self) -> None:
        self.count = 0

    def call(self, arg: Any, tag: int, caller: Any) -> None:
        self.count += 1


def _mock_redis() -> MagicMock:
    client = MagicMock()
    pubsub = MagicMock()
    client.pubsub.return_value = pubsub
    thread = MagicMock()
    thread.is_alive.return_value = True
    pubsub.run_in_thread.return_value = thread
    return client


def _run_concurrently(
    target: Any, n: int, timeout: float = 15.0
) -> list[BaseException]:
    """Start ``n`` threads on ``target(i, barrier, errors)`` released together."""
    errors: list[BaseException] = []
    barrier = threading.Barrier(n)

    def wrapped(i: int) -> None:
        try:
            barrier.wait()
            target(i, errors)
        except BaseException as exc:  # pragma: no cover - surfaced below
            errors.append(exc)

    threads = [threading.Thread(target=wrapped, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=timeout)
        assert not t.is_alive(), "a worker hung (possible deadlock)"
    return errors


# --------------------------------------------------------------------------- #
# RedisBroker pubsub / listener lifecycle
# --------------------------------------------------------------------------- #


class TestRedisLifecycleLocking:
    def test_close_vs_unsubscribe_no_attribute_error(self) -> None:
        """Concurrent close() and unsubscribe() of the last subscriber must not
        race on _pubsub (the None-check and the call are now both under the
        pubsub lock)."""
        broker = RedisBroker(_mock_redis(), allow_unregistered_classes=True)
        errors: list[BaseException] = []
        stop = threading.Event()

        def churn() -> None:
            try:
                while not stop.is_set():
                    sub = MockSubscriber()
                    broker.subscribe("c", sub)
                    broker.unsubscribe("c", sub)
            except BaseException as exc:  # pragma: no cover
                errors.append(exc)

        def closer() -> None:
            try:
                while not stop.is_set():
                    broker.close()
            except BaseException as exc:  # pragma: no cover
                errors.append(exc)

        threads = [
            threading.Thread(target=churn, daemon=True),
            threading.Thread(target=churn, daemon=True),
            threading.Thread(target=closer, daemon=True),
        ]
        for t in threads:
            t.start()
        timer = threading.Timer(2.0, stop.set)
        timer.start()
        for t in threads:
            t.join(timeout=15.0)
            assert not t.is_alive(), "redis lifecycle worker hung"
        timer.cancel()
        assert not errors, f"raced on pubsub lifecycle: {errors!r}"

    def test_concurrent_new_channels_single_pubsub_and_listener(self) -> None:
        """Many threads each subscribing a distinct brand-new channel at once
        must create exactly one pubsub object and start exactly one listener
        thread (the _ensure_pubsub / _ensure_listener check-then-act is now
        guarded)."""
        client = _mock_redis()
        broker = RedisBroker(client, allow_unregistered_classes=True)
        keep: list[MockSubscriber] = []
        keep_lock = threading.Lock()

        def subscribe_new(i: int, errors: list[BaseException]) -> None:
            sub = MockSubscriber()
            with keep_lock:
                keep.append(sub)  # keep alive so the channel persists
            broker.subscribe(f"chan-{i}", sub)

        errors = _run_concurrently(subscribe_new, n=16)
        assert not errors, f"raced subscribing new channels: {errors!r}"

        # One pubsub created, one listener thread started, regardless of races.
        assert client.pubsub.call_count == 1
        assert client.pubsub.return_value.run_in_thread.call_count == 1
        assert len(broker._subscribers) == 16

    def test_concurrent_same_channel_subscribes_keep_all(self) -> None:
        """Many threads subscribing distinct subscribers to the SAME new channel
        at once: the Redis-side subscribe happens once and every subscriber is
        retained (set creation is serialized under the subscriber lock)."""
        client = _mock_redis()
        broker = RedisBroker(client, allow_unregistered_classes=True)
        keep: list[MockSubscriber] = []
        keep_lock = threading.Lock()

        def subscribe_same(i: int, errors: list[BaseException]) -> None:
            sub = MockSubscriber()
            with keep_lock:
                keep.append(sub)
            broker.subscribe("shared", sub)

        errors = _run_concurrently(subscribe_same, n=16)
        assert not errors, f"raced subscribing same channel: {errors!r}"

        # Exactly one Redis-side subscribe for the single new channel.
        assert client.pubsub.return_value.subscribe.call_count == 1
        assert len(broker._subscribers["shared"]) == 16


# --------------------------------------------------------------------------- #
# MultiPublisher / MultiSubscriber bookkeeping
# --------------------------------------------------------------------------- #


class _MP(MultiPublisher):
    event1 = EventPublication(Events.EVENT_1, SampleEvent)


class TestMultiPublisherLocking:
    def test_concurrent_add_same_new_publication_keeps_all(self) -> None:
        """Threads racing to add subscribers to the same not-yet-created
        publication must all land on a single shared EventPublisher; none is
        dropped by a lost get-or-create."""
        mp = _MP()
        subs = [MockSubscriber() for _ in range(32)]

        def add(i: int, errors: list[BaseException]) -> None:
            mp.add_subscriber(_MP.event1, subs[i])

        errors = _run_concurrently(add, n=32)
        assert not errors, f"raced creating publisher: {errors!r}"

        # Exactly one publisher created; every subscriber retained.
        assert len(mp._publishers) == 1
        publisher = mp._publishers[_MP.event1]
        assert len(publisher.get_subscribers()) == 32

    def test_concurrent_add_remove_soak(self) -> None:
        """Add/remove the same publication from several threads: no exceptions,
        and the final state is internally consistent."""
        mp = _MP()
        held = [MockSubscriber() for _ in range(8)]
        errors: list[BaseException] = []
        stop = threading.Event()

        def worker(idx: int) -> None:
            try:
                while not stop.is_set():
                    mp.add_subscriber(_MP.event1, held[idx])
                    mp.remove_subscriber(_MP.event1, held[idx])
            except BaseException as exc:  # pragma: no cover
                errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=(i,), daemon=True) for i in range(8)
        ]
        for t in threads:
            t.start()
        timer = threading.Timer(2.0, stop.set)
        timer.start()
        for t in threads:
            t.join(timeout=15.0)
            assert not t.is_alive(), "multipublisher worker hung"
        timer.cancel()
        assert not errors, f"multipublisher add/remove raced: {errors!r}"
        # Publish still works and does not raise.
        mp.publish(_MP.event1, SampleEvent(value=1))


class _Pub(EventPublisher):
    def __init__(self) -> None:
        super().__init__(EventPublication(Events.EVENT_1, SampleEvent))


class _MS(MultiSubscriber):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[Any] = []

    def handle_event(self, event: Any) -> None:
        self.calls.append(event)

    @staticmethod
    def _event_adapter(
        handler: Any,
        subscriber: Any,
        arg: Any,
        current_event_tag: int,
        current_event_caller: Any,
    ) -> None:
        handler(subscriber, arg)

    # partial() has no __name__, so EventSubscription binds it via
    # ``partial(callback, subscriber)`` instead of looking up a method by name.
    event1 = EventSubscription(
        _Pub, Events.EVENT_1, partial(_event_adapter, handle_event)
    )


class TestMultiSubscriberLocking:
    def test_concurrent_add_remove_subscription_soak(self) -> None:
        """Concurrent add/remove of subscriptions across publishers must not
        raise or corrupt the nested dict."""
        ms = _MS()
        publishers = [_Pub() for _ in range(8)]
        errors: list[BaseException] = []
        stop = threading.Event()

        def worker(idx: int) -> None:
            pub = publishers[idx]
            try:
                while not stop.is_set():
                    ms.add_subscription(_MS.event1, pub)
                    ms.remove_subscription(_MS.event1, pub)
            except BaseException as exc:  # pragma: no cover
                errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=(i,), daemon=True) for i in range(8)
        ]
        for t in threads:
            t.start()
        timer = threading.Timer(2.0, stop.set)
        timer.start()
        for t in threads:
            t.join(timeout=15.0)
            assert not t.is_alive(), "multisubscriber worker hung"
        timer.cancel()
        assert not errors, f"multisubscriber add/remove raced: {errors!r}"


# --------------------------------------------------------------------------- #
# EventPublisher.broker reassignment
# --------------------------------------------------------------------------- #


class TestBrokerSwap:
    def test_broker_swap_migrates_all_subscribers(self) -> None:
        """Reassigning the broker migrates every live subscriber from the old
        broker to the new one atomically (snapshot + swap under the lock)."""
        broker_a = LocalBroker()
        broker_b = LocalBroker()
        publisher = _Pub()
        publisher.broker = broker_a

        subs = [MockSubscriber() for _ in range(20)]
        for s in subs:
            publisher.add_subscriber(s)

        channel = publisher._channel
        assert len(broker_a._subscriptions[channel]) == 20

        publisher.broker = broker_b

        # Fully migrated: old broker drained, new broker holds all subscribers.
        assert channel not in broker_a._subscriptions
        assert len(broker_b._subscriptions[channel]) == 20
        broker_b.publish(channel, SampleEvent(value=1), Events.EVENT_1, None)
        assert all(s.count == 1 for s in subs)

    def test_broker_swap_concurrent_with_add_no_loss(self) -> None:
        """Swapping the broker while another thread adds subscribers must not
        deadlock and must leave every subscriber registered on the final broker
        (it lands in the migration snapshot or registers directly on the new
        broker)."""
        broker_a = LocalBroker()
        broker_b = LocalBroker()
        publisher = _Pub()
        publisher.broker = broker_a

        held = [MockSubscriber() for _ in range(50)]
        errors: list[BaseException] = []
        start = threading.Barrier(2)

        def adder() -> None:
            try:
                start.wait()
                for s in held:
                    publisher.add_subscriber(s)
            except BaseException as exc:  # pragma: no cover
                errors.append(exc)

        def swapper() -> None:
            try:
                start.wait()
                publisher.broker = broker_b
            except BaseException as exc:  # pragma: no cover
                errors.append(exc)

        t1 = threading.Thread(target=adder, daemon=True)
        t2 = threading.Thread(target=swapper, daemon=True)
        t1.start()
        t2.start()
        t1.join(timeout=15.0)
        t2.join(timeout=15.0)
        assert not t1.is_alive() and not t2.is_alive(), "broker swap deadlocked"
        assert not errors, f"broker swap raced: {errors!r}"

        # The publisher's own set is the source of truth; reconcile and verify
        # every subscriber is live and the final broker can reach them.
        live = publisher.get_subscribers()
        assert len(live) == 50
        # Ensure all are registered on the final broker (add a fresh publish).
        channel = publisher._channel
        broker_b.publish(channel, SampleEvent(value=1), Events.EVENT_1, None)
        # Every subscriber that the swap migrated OR that registered post-swap is
        # on broker_b; any that only made it onto broker_a would be missed here.
        delivered = sum(s.count for s in held)
        assert delivered == 50, f"only {delivered}/50 subscribers on final broker"
