import asyncio
from dataclasses import dataclass

import pytest

from eventspype.sub.tracker import TrackingEventSubscriber


@dataclass
class MockEvent:
    message: str
    value: int


@dataclass
class OtherMockEvent:
    data: str


@pytest.fixture
def logger() -> TrackingEventSubscriber:
    return TrackingEventSubscriber(event_source="test_source")


def test_logger_initialization() -> None:
    # Test with event source
    logger = TrackingEventSubscriber(event_source="test_source")
    assert logger.event_source == "test_source"

    # Test without event source
    logger = TrackingEventSubscriber()
    assert logger.event_source is None

    # Test with custom max_len
    logger = TrackingEventSubscriber(max_len=10)
    assert logger._generic_collected_events.maxlen == 10


def test_event_logging(logger: TrackingEventSubscriber) -> None:
    event = MockEvent(message="test message", value=42)
    logger.call(event, 1, None)

    assert len(logger.event_log) == 1
    assert logger.event_log[0] == event


def test_event_log_max_len() -> None:
    logger = TrackingEventSubscriber(max_len=2)

    # Add three events
    events = [MockEvent(message=f"message {i}", value=i) for i in range(3)]

    for event in events:
        logger.call(event, 1, None)

    # Should only contain the last two events
    assert len(logger.event_log) == 2
    assert logger.event_log == events[1:]


def test_clear_logs(logger: TrackingEventSubscriber) -> None:
    # Add some events
    events = [MockEvent(message=f"message {i}", value=i) for i in range(3)]

    for event in events:
        logger.call(event, 1, None)

    assert len(logger.event_log) == 3

    # Clear the logs
    logger.clear()
    assert len(logger.event_log) == 0


@pytest.mark.asyncio
async def test_wait_for_event(logger: TrackingEventSubscriber) -> None:
    # Create an event to wait for
    event = MockEvent(message="test message", value=42)

    # Start waiting for the event in a task
    wait_task = asyncio.create_task(logger.wait_for(MockEvent, timeout_seconds=1))

    # Small delay to ensure the wait is started
    await asyncio.sleep(0.1)

    # Trigger the event
    logger.call(event, 1, None)

    # Wait for the result
    result = await wait_task
    assert result == event


@pytest.mark.asyncio
async def test_wait_for_timeout(logger: TrackingEventSubscriber) -> None:
    with pytest.raises(asyncio.TimeoutError):
        await logger.wait_for(MockEvent, timeout_seconds=0.1)


@pytest.mark.asyncio
async def test_wait_for_wrong_event_type(logger: TrackingEventSubscriber) -> None:
    # Start waiting for TestEvent
    wait_task = asyncio.create_task(logger.wait_for(MockEvent, timeout_seconds=0.5))

    # Small delay to ensure the wait is started
    await asyncio.sleep(0.1)

    # Trigger a different event type
    other_event = OtherMockEvent(data="test")
    logger.call(other_event, 1, None)

    # Should timeout since we never got the right event type
    with pytest.raises(asyncio.TimeoutError):
        await wait_task


@pytest.mark.asyncio
async def test_multiple_waiters(logger: TrackingEventSubscriber) -> None:
    event = MockEvent(message="test message", value=42)

    # Create multiple wait tasks
    wait_tasks = [
        asyncio.create_task(logger.wait_for(MockEvent, timeout_seconds=1))
        for _ in range(3)
    ]

    # Small delay to ensure all waits are started
    await asyncio.sleep(0.1)

    # Trigger the event
    logger.call(event, 1, None)

    # All tasks should receive the same event
    results = await asyncio.gather(*wait_tasks)
    assert all(result == event for result in results)


@pytest.mark.asyncio
async def test_wait_cleanup(logger: TrackingEventSubscriber) -> None:
    # Start waiting for an event
    wait_task = asyncio.create_task(logger.wait_for(MockEvent, timeout_seconds=0.1))

    # Let it timeout
    with pytest.raises(asyncio.TimeoutError):
        await wait_task

    # Check that internal state was cleaned up
    assert not logger._waiting
    assert not logger._wait_returns
