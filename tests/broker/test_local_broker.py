import logging
import weakref
from dataclasses import dataclass
from enum import Enum
from typing import Any

import pytest

from eventspype.broker.broker import MessageBroker
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


def test_message_broker_abstract_publish_raises() -> None:
    """Test that calling super().publish on MessageBroker raises NotImplementedError (line 26)."""

    class BarePublishBroker(MessageBroker):
        def publish(
            self, channel: str, event: Any, event_tag: int, caller: Any
        ) -> None:
            super().publish(channel, event, event_tag, caller)  # type: ignore[safe-super]

        def subscribe(self, channel: str, subscriber: EventSubscriber) -> None:
            pass

        def unsubscribe(self, channel: str, subscriber: EventSubscriber) -> None:
            pass

    broker = BarePublishBroker()
    with pytest.raises(NotImplementedError):
        broker.publish("ch", None, 1, None)


def test_message_broker_abstract_subscribe_raises() -> None:
    """Test that calling super().subscribe on MessageBroker raises NotImplementedError (line 36)."""

    class BareSubscribeBroker(MessageBroker):
        def publish(
            self, channel: str, event: Any, event_tag: int, caller: Any
        ) -> None:
            pass

        def subscribe(self, channel: str, subscriber: EventSubscriber) -> None:
            super().subscribe(channel, subscriber)  # type: ignore[safe-super]

        def unsubscribe(self, channel: str, subscriber: EventSubscriber) -> None:
            pass

    broker = BareSubscribeBroker()
    with pytest.raises(NotImplementedError):
        broker.subscribe("ch", None)  # type: ignore[arg-type]


def test_message_broker_abstract_unsubscribe_raises() -> None:
    """Test that calling super().unsubscribe on MessageBroker raises NotImplementedError (line 46)."""

    class BareUnsubscribeBroker(MessageBroker):
        def publish(
            self, channel: str, event: Any, event_tag: int, caller: Any
        ) -> None:
            pass

        def subscribe(self, channel: str, subscriber: EventSubscriber) -> None:
            pass

        def unsubscribe(self, channel: str, subscriber: EventSubscriber) -> None:
            super().unsubscribe(channel, subscriber)  # type: ignore[safe-super]

    broker = BareUnsubscribeBroker()
    with pytest.raises(NotImplementedError):
        broker.unsubscribe("ch", None)  # type: ignore[arg-type]


def test_local_broker_dead_subscriber_during_publish(broker: LocalBroker) -> None:
    """Test that dead subscriber refs are skipped during publish (line 38)."""
    live_subscriber = MockSubscriber()

    class TempSubscriber(EventSubscriber):
        def call(
            self, arg: Any, current_event_tag: int, current_event_caller: Any
        ) -> None:
            pass

    temp = TempSubscriber()
    broker.subscribe("test_channel", live_subscriber)
    broker.subscribe("test_channel", temp)

    # Kill the temp subscriber
    del temp

    # Inject a guaranteed dead ref into the subscription set
    another = TempSubscriber()
    dead_ref: weakref.ReferenceType[EventSubscriber] = weakref.ref(another)
    broker._subscriptions["test_channel"].add(dead_ref)
    del another  # Now dead_ref() returns None

    # Publish should skip dead refs and deliver to live subscriber
    broker.publish("test_channel", Event1(message="hello"), 1, None)

    assert len(live_subscriber.received_messages) == 1
    assert live_subscriber.received_messages[0] == Event1(message="hello")
