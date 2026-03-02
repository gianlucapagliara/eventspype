"""
Tests for the type-indexed waiter lookup in TrackingEventSubscriber.

Verifies that the new _waiting_by_type dict correctly indexes waiters
by event type for O(1) lookup, and that cleanup is correct across
concurrent waiters, timeouts, and multiple event types.
"""

import asyncio
from dataclasses import dataclass

import pytest

from eventspype.sub.tracker import TrackingEventSubscriber


@dataclass
class AlphaEvent:
    value: int


@dataclass
class BetaEvent:
    data: str


@dataclass
class GammaEvent:
    flag: bool


@pytest.fixture
def tracker() -> TrackingEventSubscriber:
    return TrackingEventSubscriber(event_source="test")


class TestTypeIndexedWaiterLookup:
    @pytest.mark.asyncio
    async def test_waiter_only_notified_for_matching_type(
        self, tracker: TrackingEventSubscriber
    ) -> None:
        """A waiter for AlphaEvent should NOT be notified by BetaEvent."""
        wait_task = asyncio.create_task(
            tracker.wait_for(AlphaEvent, timeout_seconds=0.3)
        )
        await asyncio.sleep(0.05)

        # Deliver a BetaEvent — should NOT trigger the AlphaEvent waiter
        tracker.call(BetaEvent(data="nope"), 1, None)

        with pytest.raises(asyncio.TimeoutError):
            await wait_task

    @pytest.mark.asyncio
    async def test_concurrent_waiters_different_types(
        self, tracker: TrackingEventSubscriber
    ) -> None:
        """Waiters for different types should be independently notified."""
        alpha_task = asyncio.create_task(
            tracker.wait_for(AlphaEvent, timeout_seconds=1)
        )
        beta_task = asyncio.create_task(
            tracker.wait_for(BetaEvent, timeout_seconds=1)
        )
        await asyncio.sleep(0.05)

        alpha_event = AlphaEvent(value=42)
        beta_event = BetaEvent(data="hello")

        tracker.call(alpha_event, 1, None)
        tracker.call(beta_event, 2, None)

        alpha_result = await alpha_task
        beta_result = await beta_task

        assert alpha_result == alpha_event
        assert beta_result == beta_event

    @pytest.mark.asyncio
    async def test_multiple_waiters_same_type_all_notified(
        self, tracker: TrackingEventSubscriber
    ) -> None:
        """Multiple waiters for the same type should all receive the event."""
        tasks = [
            asyncio.create_task(tracker.wait_for(AlphaEvent, timeout_seconds=1))
            for _ in range(5)
        ]
        await asyncio.sleep(0.05)

        event = AlphaEvent(value=99)
        tracker.call(event, 1, None)

        results = await asyncio.gather(*tasks)
        assert all(r == event for r in results)

    @pytest.mark.asyncio
    async def test_cleanup_after_successful_wait(
        self, tracker: TrackingEventSubscriber
    ) -> None:
        """After a successful wait, the waiter should be cleaned up."""
        task = asyncio.create_task(
            tracker.wait_for(AlphaEvent, timeout_seconds=1)
        )
        await asyncio.sleep(0.05)

        tracker.call(AlphaEvent(value=1), 1, None)
        await task

        # Internal state should be clean
        assert AlphaEvent not in tracker._waiting_by_type
        assert not tracker._wait_returns

    @pytest.mark.asyncio
    async def test_cleanup_after_timeout(
        self, tracker: TrackingEventSubscriber
    ) -> None:
        """After a timeout, the waiter should be cleaned up."""
        task = asyncio.create_task(
            tracker.wait_for(AlphaEvent, timeout_seconds=0.1)
        )
        with pytest.raises(asyncio.TimeoutError):
            await task

        assert AlphaEvent not in tracker._waiting_by_type
        assert not tracker._wait_returns

    @pytest.mark.asyncio
    async def test_partial_cleanup_when_some_waiters_remain(
        self, tracker: TrackingEventSubscriber
    ) -> None:
        """When one waiter times out but others remain, only the timed-out one
        should be removed from the type's waiter set."""
        # Start two waiters for AlphaEvent — one short timeout, one long
        short_task = asyncio.create_task(
            tracker.wait_for(AlphaEvent, timeout_seconds=0.1)
        )
        long_task = asyncio.create_task(
            tracker.wait_for(AlphaEvent, timeout_seconds=2)
        )
        await asyncio.sleep(0.05)

        # Short timeout should fire
        with pytest.raises(asyncio.TimeoutError):
            await short_task

        # The type key should still exist because long_task is still waiting
        assert AlphaEvent in tracker._waiting_by_type
        assert len(tracker._waiting_by_type[AlphaEvent]) == 1

        # Now deliver the event for the long waiter
        event = AlphaEvent(value=100)
        tracker.call(event, 1, None)
        result = await long_task
        assert result == event

        # Now fully clean
        assert AlphaEvent not in tracker._waiting_by_type

    @pytest.mark.asyncio
    async def test_type_key_removed_when_last_waiter_cleans_up(
        self, tracker: TrackingEventSubscriber
    ) -> None:
        """The type key itself should be removed from _waiting_by_type when
        the last waiter for that type is cleaned up."""
        task = asyncio.create_task(
            tracker.wait_for(BetaEvent, timeout_seconds=0.1)
        )
        await asyncio.sleep(0.05)

        assert BetaEvent in tracker._waiting_by_type

        with pytest.raises(asyncio.TimeoutError):
            await task

        # Key should be completely removed, not left as an empty set
        assert BetaEvent not in tracker._waiting_by_type

    @pytest.mark.asyncio
    async def test_event_logged_even_with_no_waiters(
        self, tracker: TrackingEventSubscriber
    ) -> None:
        """Events should still be logged even when there are no waiters."""
        tracker.call(AlphaEvent(value=1), 1, None)
        tracker.call(AlphaEvent(value=2), 1, None)

        assert len(tracker.event_log) == 2
        assert tracker.event_log[0] == AlphaEvent(value=1)
        assert tracker.event_log[1] == AlphaEvent(value=2)

    @pytest.mark.asyncio
    async def test_interleaved_types_correct_dispatch(
        self, tracker: TrackingEventSubscriber
    ) -> None:
        """Events of different types interleaved should dispatch correctly."""
        alpha_task = asyncio.create_task(
            tracker.wait_for(AlphaEvent, timeout_seconds=1)
        )
        gamma_task = asyncio.create_task(
            tracker.wait_for(GammaEvent, timeout_seconds=1)
        )
        await asyncio.sleep(0.05)

        # Deliver gamma first, then alpha
        gamma_event = GammaEvent(flag=True)
        alpha_event = AlphaEvent(value=7)

        tracker.call(gamma_event, 3, None)
        tracker.call(alpha_event, 1, None)

        assert await alpha_task == alpha_event
        assert await gamma_task == gamma_event

    @pytest.mark.asyncio
    async def test_rapid_wait_and_deliver_cycle(
        self, tracker: TrackingEventSubscriber
    ) -> None:
        """Rapid sequential wait-deliver cycles should not leak state."""
        for i in range(10):
            task = asyncio.create_task(
                tracker.wait_for(AlphaEvent, timeout_seconds=1)
            )
            await asyncio.sleep(0.01)
            tracker.call(AlphaEvent(value=i), 1, None)
            result = await task
            assert result == AlphaEvent(value=i)

        # All state should be clean
        assert not tracker._waiting_by_type
        assert not tracker._wait_returns
