from dataclasses import dataclass
from enum import Enum
from typing import Any

import pytest

from eventspype.pub.multipublisher import MultiPublisher
from eventspype.pub.publication import EventPublication
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


class MockPublisher(MultiPublisher):
    event1 = EventPublication(MockEvents.EVENT_1, Event1)
    event2 = EventPublication(MockEvents.EVENT_2, Event2)
    not_a_publication = "this is not a publication"

    def __init__(self) -> None:
        super().__init__()
        # Pre-initialize the publishers for the test
        self._get_or_create_publisher(self.event1)
        self._get_or_create_publisher(self.event2)


class MockSubscriber(EventSubscriber):
    def __init__(self) -> None:
        self.received_messages: list[Any] = []
        self.received_tags: list[int] = []
        self.received_callers: list[MultiPublisher] = []

    def call(
        self, arg: Any, current_event_tag: int, current_event_caller: MultiPublisher
    ) -> None:
        self.received_messages.append(arg)
        self.received_tags.append(current_event_tag)
        self.received_callers.append(current_event_caller)


@pytest.fixture
def publisher() -> MockPublisher:
    return MockPublisher()


@pytest.fixture
def subscriber() -> MockSubscriber:
    return MockSubscriber()


def test_get_event_definitions(publisher: MockPublisher) -> None:
    definitions = publisher.get_event_definitions()
    assert len(definitions) == 2
    assert definitions["event1"] == MockPublisher.event1
    assert definitions["event2"] == MockPublisher.event2
    assert "not_a_publication" not in definitions


def test_add_subscriber(publisher: MockPublisher, subscriber: MockSubscriber) -> None:
    publisher.add_subscriber(MockPublisher.event1, subscriber)
    publisher.add_subscriber(MockPublisher.event2, subscriber)

    assert len(publisher._publishers) == 2
    assert MockPublisher.event1 in publisher._publishers
    assert MockPublisher.event2 in publisher._publishers


def test_add_subscriber_invalid_publication(
    publisher: MockPublisher, subscriber: MockSubscriber
) -> None:
    invalid_pub = EventPublication(
        MockEvents.EVENT_1, Event1
    )  # Not defined in TestPublisher
    with pytest.raises(ValueError, match="Invalid publication"):
        publisher.add_subscriber(invalid_pub, subscriber)


def test_remove_subscriber(
    publisher: MockPublisher, subscriber: MockSubscriber
) -> None:
    publisher.add_subscriber(MockPublisher.event1, subscriber)
    publisher.add_subscriber(MockPublisher.event2, subscriber)

    publisher.remove_subscriber(MockPublisher.event1, subscriber)
    assert MockPublisher.event1 not in publisher._publishers
    assert MockPublisher.event2 in publisher._publishers


def test_remove_nonexistent_subscriber(
    publisher: MockPublisher, subscriber: MockSubscriber
) -> None:
    # Should not raise any error
    publisher.remove_subscriber(MockPublisher.event1, subscriber)


def test_publish_event(publisher: MockPublisher, subscriber: MockSubscriber) -> None:
    publisher.add_subscriber(MockPublisher.event1, subscriber)
    event = Event1(message="test")
    publisher.publish(MockPublisher.event1, event)

    assert len(subscriber.received_messages) == 1
    assert subscriber.received_messages[0] == event
    assert subscriber.received_tags[0] == MockEvents.EVENT_1.value


def test_publish_event_invalid_type(
    publisher: MockPublisher, subscriber: MockSubscriber
) -> None:
    publisher.add_subscriber(MockPublisher.event1, subscriber)
    with pytest.raises(ValueError, match="Invalid event type"):
        publisher.publish(MockPublisher.event1, Event2(message="wrong type"))


def test_publish_event_invalid_publication(
    publisher: MockPublisher, subscriber: MockSubscriber
) -> None:
    invalid_pub = EventPublication(
        MockEvents.EVENT_1, Event1
    )  # Not defined in TestPublisher
    with pytest.raises(ValueError, match="Invalid publication"):
        publisher.publish(invalid_pub, Event1(message="test"))


def test_add_subscriber_with_callback(publisher: MockPublisher) -> None:
    messages: list[str] = []
    tags: list[int] = []

    def callback(
        arg: Event1, current_event_tag: int, current_event_caller: MultiPublisher
    ) -> None:
        print(
            f"Callback called with: arg={arg}, tag={current_event_tag}, caller={current_event_caller}"
        )
        messages.append(arg.message)
        tags.append(current_event_tag)

    # Store callback in a list to keep a reference
    callbacks = [callback]

    print(
        f"Before add_subscriber_with_callback - Publisher state: {publisher._publishers}"
    )
    publisher.add_subscriber_with_callback(MockPublisher.event1, callbacks[0])
    print(
        f"After add_subscriber_with_callback - Publisher state: {publisher._publishers}"
    )

    event1_publisher = publisher._publishers[MockPublisher.event1]
    print(f"Event1 publisher: {event1_publisher}")
    print(f"Event1 publisher subscribers: {event1_publisher._subscribers}")
    print(f"Event1 publisher get_subscribers(): {event1_publisher.get_subscribers()}")

    event = Event1(message="test")
    print(f"Triggering event: {event}")
    publisher.publish(MockPublisher.event1, event)

    assert len(messages) == 1
    assert messages[0] == "test"
    assert tags[0] == MockEvents.EVENT_1.value


def test_remove_subscriber_with_callback(publisher: MockPublisher) -> None:
    messages: list[str] = []
    tags: list[int] = []

    def callback(
        arg: Event1, current_event_tag: int, current_event_caller: MultiPublisher
    ) -> None:
        messages.append(arg.message)
        tags.append(current_event_tag)

    # Store callback in a list to keep a reference
    callbacks = [callback]

    publisher.add_subscriber_with_callback(MockPublisher.event1, callbacks[0])
    publisher.remove_subscriber_with_callback(MockPublisher.event1, callbacks[0])

    publisher.publish(MockPublisher.event1, Event1(message="test"))
    assert len(messages) == 0
    assert len(tags) == 0


def test_multiple_publishers_independence(
    publisher: MockPublisher, subscriber: MockSubscriber
) -> None:
    # Test that events from one publisher don't affect others
    publisher.add_subscriber(MockPublisher.event1, subscriber)

    # Trigger event2 should not affect subscriber
    publisher.publish(MockPublisher.event2, Event2(message="test"))
    assert len(subscriber.received_messages) == 0

    # Trigger event1 should affect subscriber
    publisher.publish(MockPublisher.event1, Event1(message="test"))
    assert len(subscriber.received_messages) == 1


class BasePublisher(MultiPublisher):
    base_event = EventPublication(MockEvents.EVENT_1, Event1)


class ChildPublisher(BasePublisher):
    # Override the base event with a different type
    base_event = EventPublication(MockEvents.EVENT_1, Event2)
    # Add a new event
    child_event = EventPublication(MockEvents.EVENT_2, Event2)


def test_event_definition_inheritance() -> None:
    # Test base class definitions
    base_defs = BasePublisher.get_event_definitions()
    assert len(base_defs) == 1
    assert "base_event" in base_defs
    assert base_defs["base_event"].event_class == Event1

    # Test child class definitions
    child_defs = ChildPublisher.get_event_definitions()
    assert len(child_defs) == 2
    # Child's override should take precedence
    assert child_defs["base_event"].event_class == Event2
    assert "child_event" in child_defs

    # Test that child's event is valid
    child = ChildPublisher()
    assert child.is_publication_valid(ChildPublisher.child_event)
    assert child.is_publication_valid(ChildPublisher.base_event)
