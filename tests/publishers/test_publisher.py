import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any
from unittest.mock import patch

import pytest

from flowevents.publishers.publications import EventPublication
from flowevents.publishers.publisher import EventPublisher
from flowevents.subscribers.subscriber import EventSubscriber


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
    assert publisher.logger.name == "flowevents.publishers.publisher"
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


def test_trigger_event(publisher: EventPublisher, subscriber: MockSubscriber) -> None:
    test_message = Event1(message="test message")
    publisher.add_subscriber(subscriber)
    publisher.trigger_event(test_message)

    assert len(subscriber.received_messages) == 1
    assert subscriber.received_messages[0] == test_message
    assert subscriber.received_tags[0] == MockEvents.EVENT_1.value
    assert subscriber.received_callers[0] == publisher


def test_multiple_subscribers() -> None:
    publication = EventPublication(MockEvents.EVENT_1, Event1)
    publisher = EventPublisher(publication)
    subscriber1 = MockSubscriber()
    subscriber2 = MockSubscriber()

    publisher.add_subscriber(subscriber1)
    publisher.add_subscriber(subscriber2)

    test_message = Event1(message="test message")
    publisher.trigger_event(test_message)

    assert subscriber1.received_messages == [test_message]
    assert subscriber2.received_messages == [test_message]


def test_invalid_event_type(
    publisher: EventPublisher, subscriber: MockSubscriber
) -> None:
    publisher.add_subscriber(subscriber)
    with pytest.raises(ValueError, match="Invalid event type"):
        publisher.trigger_event("wrong type")


def test_remove_nonexistent_subscriber(
    publisher: EventPublisher, subscriber: MockSubscriber
) -> None:
    publisher.remove_subscriber(subscriber)
    assert len(publisher.get_subscribers()) == 0


def test_trigger_event_with_error(caplog: Any) -> None:
    publication = EventPublication(MockEvents.EVENT_1, Event1)
    publisher = EventPublisher(publication)
    error_subscriber = ErrorSubscriber()
    publisher.add_subscriber(error_subscriber)

    with caplog.at_level(logging.ERROR):
        publisher.trigger_event(Event1(message="test"))

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
