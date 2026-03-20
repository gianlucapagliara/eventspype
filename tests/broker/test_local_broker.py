import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import pytest

from eventspype.broker.local import LocalBroker
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
    value: int


class MockSubscriber(EventSubscriber):
    def __init__(self) -> None:
        self.received_messages: list[Any] = []
        self.received_tags: list[int] = []

    def call(self, arg: Any, current_event_tag: int, current_event_caller: Any) -> None:
        self.received_messages.append(arg)
        self.received_tags.append(current_event_tag)


class ErrorSubscriber(EventSubscriber):
    def call(self, arg: Any, current_event_tag: int, current_event_caller: Any) -> None:
        raise ValueError("Test error")


@pytest.fixture
def broker() -> LocalBroker:
    return LocalBroker()


@pytest.fixture
def subscriber() -> MockSubscriber:
    return MockSubscriber()


def test_local_broker_publish_subscribe(
    broker: LocalBroker, subscriber: MockSubscriber
) -> None:
    broker.subscribe("test_channel", subscriber)
    broker.publish("test_channel", Event1(message="hello"), 1, None)

    assert len(subscriber.received_messages) == 1
    assert subscriber.received_messages[0] == Event1(message="hello")
    assert subscriber.received_tags[0] == 1


def test_local_broker_no_subscribers(broker: LocalBroker) -> None:
    # Should not raise when publishing to a channel with no subscribers
    broker.publish("empty_channel", Event1(message="hello"), 1, None)


def test_local_broker_unsubscribe(
    broker: LocalBroker, subscriber: MockSubscriber
) -> None:
    broker.subscribe("test_channel", subscriber)
    broker.unsubscribe("test_channel", subscriber)
    broker.publish("test_channel", Event1(message="hello"), 1, None)

    assert len(subscriber.received_messages) == 0


def test_local_broker_multiple_subscribers(broker: LocalBroker) -> None:
    sub1 = MockSubscriber()
    sub2 = MockSubscriber()
    broker.subscribe("test_channel", sub1)
    broker.subscribe("test_channel", sub2)

    broker.publish("test_channel", Event1(message="hello"), 1, None)

    assert len(sub1.received_messages) == 1
    assert len(sub2.received_messages) == 1


def test_local_broker_multiple_channels(
    broker: LocalBroker, subscriber: MockSubscriber
) -> None:
    sub2 = MockSubscriber()
    broker.subscribe("channel_a", subscriber)
    broker.subscribe("channel_b", sub2)

    broker.publish("channel_a", Event1(message="a"), 1, None)
    broker.publish("channel_b", Event2(value=42), 2, None)

    assert len(subscriber.received_messages) == 1
    assert subscriber.received_messages[0] == Event1(message="a")
    assert len(sub2.received_messages) == 1
    assert sub2.received_messages[0] == Event2(value=42)


def test_local_broker_error_handling(broker: LocalBroker, caplog: Any) -> None:
    error_sub = ErrorSubscriber()
    broker.subscribe("test_channel", error_sub)

    with caplog.at_level(logging.ERROR):
        broker.publish("test_channel", Event1(message="hello"), 1, None)

    assert len(caplog.records) == 1
    assert "Unexpected error" in caplog.records[0].message


def test_local_broker_unsubscribe_nonexistent(
    broker: LocalBroker, subscriber: MockSubscriber
) -> None:
    # Should not raise
    broker.unsubscribe("nonexistent_channel", subscriber)


def test_publisher_with_local_broker() -> None:
    """Test EventPublisher using a LocalBroker for dispatch."""
    broker = LocalBroker()
    publication = EventPublication(MockEvents.EVENT_1, Event1)
    publisher = EventPublisher(publication, broker=broker)
    subscriber = MockSubscriber()

    publisher.add_subscriber(subscriber)
    publisher.publish(Event1(message="via broker"))

    assert len(subscriber.received_messages) == 1
    assert subscriber.received_messages[0] == Event1(message="via broker")


def test_publisher_broker_property() -> None:
    """Test setting broker via property migrates subscribers."""
    publication = EventPublication(MockEvents.EVENT_1, Event1)
    publisher = EventPublisher(publication)
    subscriber = MockSubscriber()
    publisher.add_subscriber(subscriber)

    # Initially no broker - direct dispatch works
    publisher.publish(Event1(message="direct"))
    assert len(subscriber.received_messages) == 1

    # Set broker - should migrate subscribers
    broker = LocalBroker()
    publisher.broker = broker

    publisher.publish(Event1(message="via broker"))
    assert len(subscriber.received_messages) == 2
    assert subscriber.received_messages[1] == Event1(message="via broker")
