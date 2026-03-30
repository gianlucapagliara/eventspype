import logging
import weakref
from dataclasses import dataclass
from enum import Enum
from typing import Any
from unittest.mock import patch

import pytest

from eventspype.broker.local import LocalBroker
from eventspype.event import normalize_event_tag
from eventspype.pub.publication import EventPublication
from eventspype.pub.publisher import EventPublisher
from eventspype.sub.subscriber import EventSubscriber


class MockEvents(Enum):
    EVENT_1 = 1
    EVENT_2 = 2


@dataclass
class Event1:
    message: str


@dataclass
class Event2:
    message: str


class MockSubscriber(EventSubscriber):
    def __init__(self) -> None:
        self.received_messages: list[Any] = []
        self.received_tags: list[int] = []
        self.received_callers: list[EventPublisher] = []

    def call(
        self, arg: Any, current_event_tag: int, current_event_caller: EventPublisher
    ) -> None:
        self.received_messages.append(arg)
        self.received_tags.append(current_event_tag)
        self.received_callers.append(current_event_caller)


class ErrorSubscriber(EventSubscriber):
    def call(
        self, arg: Any, current_event_tag: int, current_event_caller: EventPublisher
    ) -> None:
        raise ValueError("Test error")


@pytest.fixture
def event1_pub() -> EventPublication:
    return EventPublication(MockEvents.EVENT_1, Event1)


@pytest.fixture
def event2_pub() -> EventPublication:
    return EventPublication(MockEvents.EVENT_2, Event2)


@pytest.fixture
def publisher(event1_pub: EventPublication) -> EventPublisher:
    return EventPublisher(event1_pub)


@pytest.fixture
def subscriber() -> MockSubscriber:
    return MockSubscriber()


def test_publisher_name(publisher: EventPublisher) -> None:
    assert publisher.name == "EventPublisher"


def test_publisher_logger() -> None:
    publisher = EventPublisher(EventPublication(MockEvents.EVENT_1, Event1))
    assert publisher.logger.name == EventPublisher.__module__
    # Test logger caching
    assert publisher.logger is publisher.logger


def test_add_subscriber(publisher: EventPublisher, subscriber: MockSubscriber) -> None:
    publisher.add_subscriber(subscriber)
    subscribers = publisher.get_subscribers()
    assert len(subscribers) == 1
    assert subscribers[0] == subscriber


def test_remove_subscriber(
    publisher: EventPublisher, subscriber: MockSubscriber
) -> None:
    publisher.add_subscriber(subscriber)
    publisher.remove_subscriber(subscriber)
    subscribers = publisher.get_subscribers()
    assert len(subscribers) == 0


def test_publish_event(publisher: EventPublisher, subscriber: MockSubscriber) -> None:
    test_message = Event1(message="test message")
    publisher.add_subscriber(subscriber)
    publisher.publish(test_message)

    assert len(subscriber.received_messages) == 1
    assert subscriber.received_messages[0] == test_message
    assert subscriber.received_tags[0] == normalize_event_tag(MockEvents.EVENT_1)
    assert subscriber.received_callers[0] == publisher


def test_multiple_subscribers() -> None:
    publication = EventPublication(MockEvents.EVENT_1, Event1)
    publisher = EventPublisher(publication)
    subscriber1 = MockSubscriber()
    subscriber2 = MockSubscriber()

    publisher.add_subscriber(subscriber1)
    publisher.add_subscriber(subscriber2)

    test_message = Event1(message="test message")
    publisher.publish(test_message)

    assert subscriber1.received_messages == [test_message]
    assert subscriber2.received_messages == [test_message]


def test_invalid_event_type(
    publisher: EventPublisher, subscriber: MockSubscriber
) -> None:
    publisher.add_subscriber(subscriber)
    with pytest.raises(ValueError, match="Invalid event type"):
        publisher.publish("wrong type")


def test_remove_nonexistent_subscriber(
    publisher: EventPublisher, subscriber: MockSubscriber
) -> None:
    publisher.remove_subscriber(subscriber)
    assert len(publisher.get_subscribers()) == 0


def test_publish_event_with_error(caplog: Any) -> None:
    publication = EventPublication(MockEvents.EVENT_1, Event1)
    publisher = EventPublisher(publication)
    error_subscriber = ErrorSubscriber()
    publisher.add_subscriber(error_subscriber)

    with caplog.at_level(logging.ERROR):
        publisher.publish(Event1(message="test"))

        assert len(caplog.records) == 1
        assert "Unexpected error while processing event" in caplog.records[0].message
        assert caplog.records[0].exc_info is not None


@patch("random.random")
def test_gc_on_add_subscriber(
    mock_random: Any, publisher: EventPublisher, subscriber: MockSubscriber
) -> None:
    # Force GC to run by setting random value below threshold
    mock_random.return_value = 0.001  # Below ADD_SUBSCRIBER_GC_PROBABILITY

    # Add a dead subscriber first
    class TempSubscriber(EventSubscriber):
        def call(
            self, arg: Any, current_event_tag: int, current_event_caller: EventPublisher
        ) -> None:
            pass

    temp = TempSubscriber()
    publisher.add_subscriber(temp)
    del temp  # Make the subscriber dead

    # Add new subscriber, which should trigger GC
    publisher.add_subscriber(subscriber)

    # Only the new subscriber should remain
    subscribers = publisher.get_subscribers()
    assert len(subscribers) == 1
    assert subscribers[0] == subscriber


def test_broker_property_getter() -> None:
    """Test that the broker property getter returns the broker (line 50)."""
    publication = EventPublication(MockEvents.EVENT_1, Event1)
    broker = LocalBroker()
    publisher = EventPublisher(publication, broker=broker)
    assert publisher.broker is broker

    publisher_no_broker = EventPublisher(publication)
    assert publisher_no_broker.broker is None


def test_broker_setter_migrates_from_old_broker() -> None:
    """Test broker setter with old_broker not None migrates subscribers (line 63)."""
    publication = EventPublication(MockEvents.EVENT_1, Event1)
    old_broker = LocalBroker()
    new_broker = LocalBroker()
    publisher = EventPublisher(publication, broker=old_broker)
    subscriber = MockSubscriber()

    publisher.add_subscriber(subscriber)

    # Verify subscriber works via old broker
    publisher.publish(Event1(message="via old"))
    assert len(subscriber.received_messages) == 1

    # Switch broker - should migrate subscribers from old to new
    publisher.broker = new_broker

    # Verify subscriber works via new broker
    publisher.publish(Event1(message="via new"))
    assert len(subscriber.received_messages) == 2
    assert subscriber.received_messages[1] == Event1(message="via new")

    # Verify old broker no longer dispatches to subscriber
    old_broker.publish(
        str(normalize_event_tag(MockEvents.EVENT_1)),
        Event1(message="stale"),
        normalize_event_tag(MockEvents.EVENT_1),
        publisher,
    )
    assert len(subscriber.received_messages) == 2  # no new messages


def test_remove_subscriber_with_broker() -> None:
    """Test remove_subscriber calls broker.unsubscribe when broker is set (line 91)."""
    publication = EventPublication(MockEvents.EVENT_1, Event1)
    broker = LocalBroker()
    publisher = EventPublisher(publication, broker=broker)
    subscriber = MockSubscriber()

    publisher.add_subscriber(subscriber)
    publisher.publish(Event1(message="before remove"))
    assert len(subscriber.received_messages) == 1

    publisher.remove_subscriber(subscriber)

    # After removal, publishing should not reach the subscriber
    publisher.publish(Event1(message="after remove"))
    assert len(subscriber.received_messages) == 1  # still 1


def test_dispatch_local_dead_subscriber_ref() -> None:
    """Test that dead subscriber refs are skipped during _dispatch_local (line 134)."""
    publication = EventPublication(MockEvents.EVENT_1, Event1)
    publisher = EventPublisher(publication)

    # Add a temporary subscriber that will become dead
    class TempSubscriber(EventSubscriber):
        def call(
            self, arg: Any, current_event_tag: int, current_event_caller: EventPublisher
        ) -> None:
            pass

    live_subscriber = MockSubscriber()
    temp = TempSubscriber()

    publisher.add_subscriber(temp)
    publisher.add_subscriber(live_subscriber)

    # Kill the temp subscriber - its weak ref will return None
    del temp

    # Manually add a dead ref to ensure it's present during iteration
    # (GC in _dispatch_local may clean it, but the continue on line 134 should handle it)

    another = TempSubscriber()
    dead_ref: weakref.ReferenceType[EventSubscriber] = weakref.ref(another)
    publisher._subscribers.add(dead_ref)
    del another  # Now dead_ref() returns None

    # Publish should succeed, only live_subscriber receives the event
    publisher.publish(Event1(message="test"))
    assert len(live_subscriber.received_messages) == 1
    assert live_subscriber.received_messages[0] == Event1(message="test")
