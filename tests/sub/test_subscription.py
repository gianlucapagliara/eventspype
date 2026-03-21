from dataclasses import dataclass
from enum import Enum
from typing import Any

import pytest

from eventspype.event import EventTag
from eventspype.pub.multipublisher import MultiPublisher
from eventspype.pub.publication import EventPublication
from eventspype.pub.publisher import EventPublisher
from eventspype.sub.functional import FunctionalEventSubscriber
from eventspype.sub.subscription import EventSubscription, PublicationSubscription


class MockEvents(Enum):
    EVENT_1 = 1
    EVENT_2 = 2


class MockSubscriber:
    def __init__(self) -> None:
        self.calls: list[Any] = []

    def callback(
        self, arg: Any, current_event_tag: EventTag, current_event_caller: Any
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
    def callback(arg: Any) -> Any:
        return arg

    subscription = EventSubscription(MockPublisher, MockEvents.EVENT_1, callback)

    assert subscription.publisher_class == MockPublisher
    assert subscription.event_tag == MockEvents.EVENT_1
    assert subscription.callback == callback
    assert subscription.callback_with_subscriber is True


def test_event_subscription_hash() -> None:
    def callback(arg: Any) -> Any:
        return arg

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

    subscribers = subscription.subscribe(publisher, subscriber)
    assert len(subscribers) == 1
    assert isinstance(subscribers[0], FunctionalEventSubscriber)

    # Test the subscription works
    test_message = "test"
    publisher.publish(test_message)
    assert len(subscriber.calls) == 1
    assert subscriber.calls[0] == test_message


def test_event_subscription_subscribe_multiple_events(
    mock_publication: EventPublication,
) -> None:
    subscriber = MockSubscriber()
    publisher = MockPublisher(mock_publication)
    events: list[EventTag] = [MockEvents.EVENT_1, MockEvents.EVENT_2]
    subscription = EventSubscription(
        MockPublisher, events, subscriber.callback, callback_with_subscriber=False
    )

    subscribers = subscription.subscribe(publisher, subscriber)
    assert len(subscribers) == 2

    # Test both subscriptions work - each event is received by all subscribers
    test_message1 = "test1"
    test_message2 = "test2"
    publisher.publish(test_message1)
    publisher.publish(test_message2)
    assert len(subscriber.calls) == 4  # Each message is received by both subscribers
    assert subscriber.calls[0:2] == [
        test_message1,
        test_message1,
    ]  # First message received by both subscribers
    assert subscriber.calls[2:4] == [
        test_message2,
        test_message2,
    ]  # Second message received by both subscribers


def test_event_subscription_unsubscribe(mock_publication: EventPublication) -> None:
    subscriber = MockSubscriber()
    publisher = MockPublisher(mock_publication)
    subscription = EventSubscription(
        MockPublisher,
        MockEvents.EVENT_1,
        subscriber.callback,
        callback_with_subscriber=False,
    )

    subscribers = subscription.subscribe(publisher, subscriber)
    subscription.unsubscribe(publisher, subscribers[0])

    # Test the subscription is removed
    publisher.publish("test")
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

    def callback(arg: Any, event_tag: EventTag, caller: Any) -> None:
        pass

    subscription = EventSubscription(
        MockPublisher, MockEvents.EVENT_1, callback, callback_with_subscriber=False
    )
    subscribers = subscription.subscribe(publisher, None)
    assert len(subscribers) == 1


def test_event_subscription_missing_subscriber(
    mock_publication: EventPublication,
) -> None:
    publisher = MockPublisher(mock_publication)

    def callback(subscriber: Any, arg: Any, event_tag: EventTag, caller: Any) -> None:
        pass

    subscription = EventSubscription(MockPublisher, MockEvents.EVENT_1, callback)
    with pytest.raises(
        ValueError, match="Subscriber is required for callback with subscriber"
    ):
        subscription.subscribe(publisher, None)


def test_event_tag_str_single() -> None:
    def callback(arg: Any) -> Any:
        return arg

    subscription = EventSubscription(MockPublisher, MockEvents.EVENT_1, callback)
    assert subscription.event_tag_str == str(MockEvents.EVENT_1)


def test_event_tag_str_multiple() -> None:
    def callback(arg: Any) -> Any:
        return arg

    events: list[EventTag] = [MockEvents.EVENT_1, MockEvents.EVENT_2]
    subscription = EventSubscription(MockPublisher, events, callback)
    assert subscription.event_tag_str == f"[{MockEvents.EVENT_1}, {MockEvents.EVENT_2}]"


def test_unsubscribe_publisher_type_mismatch() -> None:
    class CustomPublisher:
        pass

    subscription = EventSubscription(EventPublisher, 1, lambda event: event.arg)
    wrong_publisher = CustomPublisher()
    subscriber = FunctionalEventSubscriber(lambda event: event.arg)

    with pytest.raises(ValueError, match="Publisher type mismatch"):
        subscription._unsubscribe(wrong_publisher, subscriber, 1)  # type: ignore


def test_event_subscription_invalid_publisher_class() -> None:
    class NotAPublisher:
        pass

    with pytest.raises(
        ValueError,
        match="Publisher class must be a subclass of EventPublisher or MultiPublisher",
    ):
        EventSubscription(NotAPublisher, MockEvents.EVENT_1, lambda arg: arg)  # type: ignore


def test_get_event_tags_unknown_type() -> None:
    subscription = EventSubscription(
        MockPublisher,
        MockEvents.EVENT_1,
        lambda arg: arg,
        callback_with_subscriber=False,
    )
    # Pass an object of unknown type (not Enum, int, or str) — should raise ValueError
    with pytest.raises(ValueError, match="Invalid event tag"):
        subscription._get_event_tags([3.14])  # type: ignore


# === MultiPublisher integration tests ===


@dataclass
class Event1:
    message: str


@dataclass
class Event2:
    message: str


class MockMultiPublisher(MultiPublisher):
    event1 = EventPublication(MockEvents.EVENT_1, Event1)
    event2 = EventPublication(MockEvents.EVENT_2, Event2)


class MockMultiSubscriber:
    def __init__(self) -> None:
        self.calls: list[Any] = []

    def callback(
        self, arg: Any, current_event_tag: EventTag, current_event_caller: Any
    ) -> Any:
        self.calls.append(arg)


def test_subscribe_with_multipublisher() -> None:
    subscriber = MockMultiSubscriber()
    publisher = MockMultiPublisher()

    subscription = EventSubscription(
        MockMultiPublisher,
        MockEvents.EVENT_1,
        subscriber.callback,
        callback_with_subscriber=False,
    )

    subscribers = subscription.subscribe(publisher, subscriber)
    assert len(subscribers) == 1

    event = Event1(message="hello")
    publisher.publish(MockMultiPublisher.event1, event)
    assert len(subscriber.calls) == 1
    assert subscriber.calls[0] == event


def test_unsubscribe_with_multipublisher() -> None:
    subscriber = MockMultiSubscriber()
    publisher = MockMultiPublisher()

    subscription = EventSubscription(
        MockMultiPublisher,
        MockEvents.EVENT_1,
        subscriber.callback,
        callback_with_subscriber=False,
    )

    subs = subscription.subscribe(publisher, subscriber)
    subscription.unsubscribe(publisher, subs[0])

    publisher.publish(MockMultiPublisher.event1, Event1(message="hello"))
    assert len(subscriber.calls) == 0


def test_subscribe_callback_with_subscriber_has_name() -> None:
    """Test _subscribe with callback_with_subscriber=True and callback that has __name__."""

    class MySubscriber:
        def __init__(self) -> None:
            self.calls: list[Any] = []

        def my_callback(
            self, arg: Any, current_event_tag: EventTag, current_event_caller: Any
        ) -> Any:
            self.calls.append(arg)

    subscriber = MySubscriber()
    publisher = MockPublisher()

    # Use a named function as callback
    subscription = EventSubscription(
        MockPublisher,
        MockEvents.EVENT_1,
        MySubscriber.my_callback,
        callback_with_subscriber=True,
    )

    subs = subscription.subscribe(publisher, subscriber)
    assert len(subs) == 1

    publisher.publish("test_message")
    assert len(subscriber.calls) == 1
    assert subscriber.calls[0] == "test_message"


# === PublicationSubscription tests ===


def test_publication_subscription_init() -> None:
    def callback(arg: Any, tag: EventTag, caller: Any) -> Any:
        pass

    pub = EventPublication(MockEvents.EVENT_1, Event1)
    subscription = PublicationSubscription(
        MockMultiPublisher, pub, callback, callback_with_subscriber=False
    )

    assert subscription.publisher_class == MockMultiPublisher
    assert subscription._event_publication is pub


def test_publication_subscription_invalid_publisher_class() -> None:
    pub = EventPublication(MockEvents.EVENT_1, Event1)

    with pytest.raises(
        ValueError, match="Publisher class must be a subclass of MultiPublisher"
    ):
        PublicationSubscription(
            EventPublisher,  # type: ignore[arg-type]
            pub,
            lambda arg: arg,
            callback_with_subscriber=False,
        )


def test_publication_subscription_get_publication() -> None:
    pub = MockMultiPublisher.event1

    subscription = PublicationSubscription(
        MockMultiPublisher, pub, lambda arg: arg, callback_with_subscriber=False
    )

    publisher = MockMultiPublisher()
    result = subscription._get_publication(publisher, MockEvents.EVENT_1)
    assert result is pub
