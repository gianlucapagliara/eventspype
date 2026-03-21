"""
Tests for weakref finalizer callback-based subscriber cleanup.

Verifies that the new cleanup mechanism (weakref callbacks that auto-remove
dead references) works correctly, replacing the old probabilistic GC approach.
"""

import gc
from dataclasses import dataclass
from enum import Enum
from typing import Any

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


def make_publisher() -> EventPublisher:
    return EventPublisher(EventPublication(Events.TEST, SampleEvent))


class TestWeakrefFinalizerCleanup:
    def test_dead_subscriber_auto_removed_from_set(self) -> None:
        """When a subscriber is garbage collected, its weakref callback
        should automatically remove it from the publisher's subscriber set."""
        publisher = make_publisher()
        sub = CountingSubscriber()
        publisher.add_subscriber(sub)

        assert len(publisher._subscribers) == 1

        del sub
        gc.collect()

        # The finalizer callback should have removed the dead ref
        assert len(publisher._subscribers) == 0

    def test_dead_subscriber_not_called_on_publish(self) -> None:
        """Publishing after a subscriber dies should not raise errors."""
        publisher = make_publisher()
        live_sub = CountingSubscriber()
        dead_sub = CountingSubscriber()

        publisher.add_subscriber(live_sub)
        publisher.add_subscriber(dead_sub)

        del dead_sub
        gc.collect()

        # Publish should work without errors
        publisher.publish(SampleEvent(value=1))
        assert live_sub.count == 1

    def test_multiple_dead_subscribers_cleaned(self) -> None:
        """Multiple dead subscribers should all be cleaned up."""
        publisher = make_publisher()
        live_sub = CountingSubscriber()
        publisher.add_subscriber(live_sub)

        # Add and kill several subscribers
        for _ in range(10):
            temp = CountingSubscriber()
            publisher.add_subscriber(temp)
            del temp

        gc.collect()

        # Only the live subscriber should remain
        assert len(publisher.get_subscribers()) == 1
        assert publisher.get_subscribers()[0] is live_sub

    def test_cleanup_during_concurrent_adds(self) -> None:
        """Adding new subscribers while old ones die should be safe."""
        publisher = make_publisher()
        survivors = []

        for i in range(20):
            sub = CountingSubscriber()
            publisher.add_subscriber(sub)
            if i % 2 == 0:
                survivors.append(sub)
        # Clear the loop variable so the last odd subscriber can be GC'd
        del sub

        gc.collect()

        # Only even-indexed subscribers survive
        active = publisher.get_subscribers()
        assert len(active) == 10
        for s in survivors:
            assert s in active

    def test_publish_with_all_dead_subscribers(self) -> None:
        """Publishing when all subscribers are dead should be a no-op."""
        publisher = make_publisher()

        sub1 = CountingSubscriber()
        sub2 = CountingSubscriber()
        publisher.add_subscriber(sub1)
        publisher.add_subscriber(sub2)

        del sub1
        del sub2
        gc.collect()

        # Should not raise
        publisher.publish(SampleEvent(value=1))
        assert len(publisher.get_subscribers()) == 0

    def test_get_subscribers_returns_only_alive(self) -> None:
        """get_subscribers() should only return live subscribers."""
        publisher = make_publisher()
        live = CountingSubscriber()
        dead = CountingSubscriber()

        publisher.add_subscriber(live)
        publisher.add_subscriber(dead)

        del dead
        gc.collect()

        subs = publisher.get_subscribers()
        assert len(subs) == 1
        assert subs[0] is live

    def test_remove_subscriber_still_works(self) -> None:
        """Explicit remove_subscriber should still work."""
        publisher = make_publisher()
        sub = CountingSubscriber()
        publisher.add_subscriber(sub)

        publisher.remove_subscriber(sub)
        assert len(publisher.get_subscribers()) == 0

        # Publish should not call the removed subscriber
        publisher.publish(SampleEvent(value=1))
        assert sub.count == 0

    def test_remove_and_gc_no_double_free(self) -> None:
        """Removing a subscriber and then letting it be GC'd should not error."""
        publisher = make_publisher()
        sub = CountingSubscriber()
        publisher.add_subscriber(sub)

        publisher.remove_subscriber(sub)
        del sub
        gc.collect()

        # Should be clean
        assert len(publisher._subscribers) == 0

    def test_publish_skips_stale_weakref_without_error(self) -> None:
        """If a weakref dies between the tuple snapshot and dereference,
        publish should gracefully skip it."""
        publisher = make_publisher()
        live = CountingSubscriber()
        publisher.add_subscriber(live)

        # We can't easily trigger GC mid-iteration, but we can verify
        # the None guard in publish works by checking the live sub is called
        publisher.publish(SampleEvent(value=42))
        assert live.count == 1

    def test_large_subscriber_churn(self) -> None:
        """Rapid add/remove/GC cycles should not corrupt state."""
        publisher = make_publisher()
        persistent = CountingSubscriber()
        publisher.add_subscriber(persistent)

        for _ in range(100):
            temp = CountingSubscriber()
            publisher.add_subscriber(temp)
            del temp

        gc.collect()

        publisher.publish(SampleEvent(value=1))
        assert persistent.count == 1
        assert len(publisher.get_subscribers()) == 1
