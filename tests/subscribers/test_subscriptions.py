from enum import Enum
from typing import Any

import pytest

from flowevents.publishers.publications import EventPublication
from flowevents.publishers.publisher import EventPublisher
from flowevents.subscribers.functional import FunctionalEventSubscriber
from flowevents.subscribers.subscriptions import EventSubscription


class MockEvents(Enum):
    EVENT_1 = 1
    EVENT_2 = 2


class MockSubscriber:
    def __init__(self) -> None:
        self.calls: list[Any] = []

    def callback(
        self, arg: Any, current_event_tag: int, current_event_caller: EventPublisher
    ) -> None:
        self.calls.append(arg)


@pytest.fixture
def mock_publication() -> EventPublication:
    return EventPublication(MockEvents.EVENT_1, str)


class MockPublisher(EventPublisher):
    def __init__(self, publication: EventPublication | None = None) -> None:
        super().__init__(publication or EventPublication(MockEvents.EVENT_1, str))


class WrongPublisher(EventPublisher):
    def __init__(self, publication: EventPublication | None = None) -> None:
        super().__init__(publication or EventPublication(MockEvents.EVENT_1, str))


def test_event_subscription_init() -> None:
    def callback() -> None:
        pass

    subscription = EventSubscription(MockPublisher, MockEvents.EVENT_1, callback)

    assert subscription.publisher_class == MockPublisher
    assert subscription.event_tag == MockEvents.EVENT_1
    assert subscription.callback == callback
    assert subscription.callback_with_subscriber is True


def test_event_subscription_hash() -> None:
    def callback() -> None:
        pass

    subscription1 = EventSubscription(MockPublisher, MockEvents.EVENT_1, callback)
    subscription2 = EventSubscription(MockPublisher, MockEvents.EVENT_1, callback)

    assert hash(subscription1) == hash(subscription2)


def test_event_subscription_subscribe(mock_publication: EventPublication) -> None:
    subscriber = MockSubscriber()
    publisher = MockPublisher(mock_publication)
    subscription = EventSubscription(
        MockPublisher,
        MockEvents.EVENT_1,
        subscriber.callback,
        callback_with_subscriber=False,
    )

    listeners = subscription.subscribe(publisher, subscriber)
    assert len(listeners) == 1
    assert isinstance(listeners[0], FunctionalEventSubscriber)

    # Test the subscription works
    test_message = "test"
    publisher.trigger_event(test_message)
    assert len(subscriber.calls) == 1
    assert subscriber.calls[0] == test_message


def test_event_subscription_subscribe_multiple_events(
    mock_publication: EventPublication,
) -> None:
    subscriber = MockSubscriber()
    publisher = MockPublisher(mock_publication)
    events = [MockEvents.EVENT_1, MockEvents.EVENT_2]
    subscription = EventSubscription(
        MockPublisher, events, subscriber.callback, callback_with_subscriber=False
    )

    listeners = subscription.subscribe(publisher, subscriber)
    assert len(listeners) == 2

    # Test both subscriptions work - each event is received by all listeners
    test_message1 = "test1"
    test_message2 = "test2"
    publisher.trigger_event(test_message1)
    publisher.trigger_event(test_message2)
    assert len(subscriber.calls) == 4  # Each message is received by both listeners
    assert subscriber.calls[0:2] == [
        test_message1,
        test_message1,
    ]  # First message received by both listeners
    assert subscriber.calls[2:4] == [
        test_message2,
        test_message2,
    ]  # Second message received by both listeners


def test_event_subscription_unsubscribe(mock_publication: EventPublication) -> None:
    subscriber = MockSubscriber()
    publisher = MockPublisher(mock_publication)
    subscription = EventSubscription(
        MockPublisher,
        MockEvents.EVENT_1,
        subscriber.callback,
        callback_with_subscriber=False,
    )

    listeners = subscription.subscribe(publisher, subscriber)
    subscription.unsubscribe(publisher, listeners[0])

    # Test the subscription is removed
    publisher.trigger_event("test")
    assert len(subscriber.calls) == 0


def test_event_subscription_wrong_publisher(mock_publication: EventPublication) -> None:
    subscriber = MockSubscriber()
    publisher = WrongPublisher(mock_publication)
    subscription = EventSubscription(
        MockPublisher, MockEvents.EVENT_1, subscriber.callback
    )

    with pytest.raises(ValueError, match="Publisher type mismatch"):
        subscription.subscribe(publisher, subscriber)


def test_event_subscription_without_subscriber(
    mock_publication: EventPublication,
) -> None:
    publisher = MockPublisher(mock_publication)

    def callback(arg: Any, event_tag: int, caller: EventPublisher) -> None:
        pass

    subscription = EventSubscription(
        MockPublisher, MockEvents.EVENT_1, callback, callback_with_subscriber=False
    )
    listeners = subscription.subscribe(publisher, None)
    assert len(listeners) == 1


def test_event_subscription_missing_subscriber(
    mock_publication: EventPublication,
) -> None:
    publisher = MockPublisher(mock_publication)

    def callback(
        subscriber: Any, arg: Any, event_tag: int, caller: EventPublisher
    ) -> None:
        pass

    subscription = EventSubscription(MockPublisher, MockEvents.EVENT_1, callback)
    with pytest.raises(
        ValueError, match="Subscriber is required for callback with subscriber"
    ):
        subscription.subscribe(publisher, None)


def test_event_tag_str_single() -> None:
    def callback() -> None:
        pass

    subscription = EventSubscription(MockPublisher, MockEvents.EVENT_1, callback)
    assert subscription.event_tag_str == str(MockEvents.EVENT_1)


def test_event_tag_str_multiple() -> None:
    def callback() -> None:
        pass

    events = [MockEvents.EVENT_1, MockEvents.EVENT_2]
    subscription = EventSubscription(MockPublisher, events, callback)
    assert subscription.event_tag_str == f"[{MockEvents.EVENT_1}, {MockEvents.EVENT_2}]"


def test_unsubscribe_publisher_type_mismatch() -> None:
    class CustomPublisher:
        pass

    subscription = EventSubscription(
        EventPublisher, 1, lambda message, tag, publisher: message
    )
    wrong_publisher = CustomPublisher()
    listener = FunctionalEventSubscriber(lambda message, tag, publisher: message)

    with pytest.raises(ValueError, match="Publisher type mismatch"):
        subscription._unsubscribe(wrong_publisher, listener, 1)  # type: ignore
