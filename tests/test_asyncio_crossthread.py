"""Regression tests for cross-thread asyncio wakeups.

The async-bridging subscribers (TrackingEventSubscriber, QueueEventSubscriber)
receive events via ``call()``, which runs on the *publisher* thread -- and for a
RedisBroker that is always its background listener thread, never the asyncio
loop thread. asyncio.Event / asyncio.Queue are not thread-safe: calling
``notifier.set()`` / ``queue.put_nowait()`` directly from another thread fails
to wake the loop, so the awaiting coroutine hangs until its timeout (or forever
for an untimed ``await queue.get()``).

The fix marshals the wakeup onto the waiter's loop via
``loop.call_soon_threadsafe``. These tests fire ``call()`` from a separate
thread and assert the awaiting coroutine wakes promptly. They would hang to the
timeout / fail on the pre-fix code; the global ``timeout = 30`` bounds a true
regression.
"""

import asyncio
import threading
import time
from typing import Any

import pytest

from eventspype.sub.queue import QueueEventSubscriber
from eventspype.sub.tracker import TrackingEventSubscriber


class TrackedEvent:
    def __init__(self, value: int = 0) -> None:
        self.value = value


def _fire_from_thread(fn: Any, delay: float = 0.15) -> threading.Thread:
    """Run ``fn()`` on a separate (non-loop) thread after a short delay,
    mimicking a broker listener thread delivering an event."""

    def worker() -> None:
        time.sleep(delay)
        fn()

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return t


class TestTrackerCrossThread:
    @pytest.mark.asyncio
    async def test_wait_for_woken_promptly_from_other_thread(self) -> None:
        """wait_for must wake ~immediately when call() fires on another thread,
        not hang until timeout_seconds."""
        tracker = TrackingEventSubscriber()
        tracker.track_event_type(TrackedEvent)

        event = TrackedEvent(value=42)
        _fire_from_thread(lambda: tracker.call(event, 1, None))

        t0 = time.monotonic()
        # Generous timeout: a lost wakeup would make this take ~5s (or raise),
        # a correct wakeup returns in ~0.15s.
        result = await tracker.wait_for(TrackedEvent, timeout_seconds=5.0)
        elapsed = time.monotonic() - t0

        assert result is event
        assert elapsed < 1.0, (
            f"wait_for took {elapsed:.3f}s -> cross-thread wakeup was lost"
        )

    @pytest.mark.asyncio
    async def test_multiple_waiters_woken_from_other_thread(self) -> None:
        """All waiters on a type wake promptly from a single cross-thread call()."""
        tracker = TrackingEventSubscriber()
        tracker.track_event_type(TrackedEvent)

        tasks = [
            asyncio.create_task(tracker.wait_for(TrackedEvent, timeout_seconds=5.0))
            for _ in range(5)
        ]
        await asyncio.sleep(0.05)  # let all waiters register

        event = TrackedEvent(value=7)
        _fire_from_thread(lambda: tracker.call(event, 1, None))

        t0 = time.monotonic()
        results = await asyncio.gather(*tasks)
        elapsed = time.monotonic() - t0

        assert all(r is event for r in results)
        assert elapsed < 1.0, f"waiters took {elapsed:.3f}s -> wakeup lost"

    @pytest.mark.asyncio
    async def test_same_thread_wait_for_still_works(self) -> None:
        """Firing call() from the loop thread itself must still wake the waiter
        (call_soon_threadsafe is valid from the loop's own thread)."""
        tracker = TrackingEventSubscriber()
        tracker.track_event_type(TrackedEvent)
        task = asyncio.create_task(tracker.wait_for(TrackedEvent, timeout_seconds=5.0))
        await asyncio.sleep(0.05)

        event = TrackedEvent(value=1)
        tracker.call(event, 1, None)  # same (loop) thread
        result = await asyncio.wait_for(task, timeout=2.0)
        assert result is event

    @pytest.mark.asyncio
    async def test_wait_for_timeout_unchanged(self) -> None:
        """A genuine timeout (no matching event) still raises promptly."""
        tracker = TrackingEventSubscriber()
        with pytest.raises(asyncio.TimeoutError):
            await tracker.wait_for(TrackedEvent, timeout_seconds=0.1)
        # Waiter bookkeeping is cleaned up.
        assert tracker._waiting_by_type == {}
        assert tracker._notifier_loops == {}


class TestQueueCrossThread:
    @pytest.mark.asyncio
    async def test_get_woken_promptly_from_other_thread(self) -> None:
        """An awaiting queue consumer must wake when call() puts from another
        thread; pre-fix this hung (forever without an outer timeout)."""
        sub = QueueEventSubscriber()
        queue = sub.subscribe_consumer()

        _fire_from_thread(lambda: sub.call(TrackedEvent(value=99), 1, None))

        t0 = time.monotonic()
        item = await asyncio.wait_for(queue.get(), timeout=5.0)
        elapsed = time.monotonic() - t0

        assert item["event_type"] == "TrackedEvent"
        assert elapsed < 1.0, (
            f"queue.get woke after {elapsed:.3f}s -> cross-thread put was lost"
        )

    @pytest.mark.asyncio
    async def test_fan_out_to_multiple_consumers_cross_thread(self) -> None:
        """Each consumer queue is woken on its own loop from one cross-thread
        call()."""
        sub = QueueEventSubscriber()
        q1 = sub.subscribe_consumer()
        q2 = sub.subscribe_consumer()

        _fire_from_thread(lambda: sub.call(TrackedEvent(value=5), 1, None))

        got = await asyncio.wait_for(asyncio.gather(q1.get(), q2.get()), timeout=5.0)
        assert got[0]["event_type"] == "TrackedEvent"
        assert got[1]["event_type"] == "TrackedEvent"

    @pytest.mark.asyncio
    async def test_unsubscribed_consumer_not_woken(self) -> None:
        """After unsubscribe, a cross-thread call() must not deliver to the
        removed queue (and must not raise)."""
        sub = QueueEventSubscriber()
        queue = sub.subscribe_consumer()
        sub.unsubscribe_consumer(queue)
        assert sub.consumer_count == 0

        t = _fire_from_thread(lambda: sub.call(TrackedEvent(value=1), 1, None))
        t.join(timeout=5.0)
        await asyncio.sleep(0.1)  # let any erroneously-scheduled put run
        assert queue.empty()

    def test_sync_subscribe_without_loop_delivers_directly(self) -> None:
        """When subscribe_consumer is called with no running loop, call()
        delivers synchronously (legacy behavior) so get_nowait works at once."""
        sub = QueueEventSubscriber()
        queue = sub.subscribe_consumer()  # no running loop here
        sub.call(TrackedEvent(value=3), 1, None)
        item = queue.get_nowait()
        assert item["event_type"] == "TrackedEvent"
