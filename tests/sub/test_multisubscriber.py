import logging
from enum import Enum
from functools import partial
from typing import Any

import pytest

from eventspype.pub.publication import EventPublication
from eventspype.pub.publisher import EventPublisher
from eventspype.sub.multisubscriber import MultiSubscriber
from eventspype.sub.subscription import EventSubscription


class MockEvents(Enum):
    EVENT_1 = 1
    EVENT_2 = 2


@pytest.fixture
def mock_publication() -> EventPublication:
    return EventPublication(MockEvents.EVENT_1, str)


class MockPublisher(EventPublisher):
    def __init__(self, publication: EventPublication | None = None) -> None:
        super().__init__(publication or EventPublication(MockEvents.EVENT_1, str))


class MockMultiSubscriber(MultiSubscriber):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[Any] = []
        self._logger = logging.getLogger(__name__)

    def logger(self) -> logging.Logger:
        return self._logger

    def handle_event(self, event: Any) -> None:
        self.calls.append(event)

    @staticmethod
    def _event_adapter(
        handler: Any,
        subscriber: Any,
        arg: Any,
        current_event_tag: int,
        current_event_caller: EventPublisher,
    ) -> None:
        handler(subscriber, arg)

    # Define event subscriptions as class attributes
    event1 = EventSubscription(
        MockPublisher, MockEvents.EVENT_1, partial(_event_adapter, handle_event)
    )
    event2 = EventSubscription(
        MockPublisher, MockEvents.EVENT_2, partial(_event_adapter, handle_event)
    )


def test_multi_subscriber_get_event_definitions() -> None:
    subscriber = MockMultiSubscriber()
    definitions = subscriber.get_event_definitions()

    assert len(definitions) == 2
    assert "event1" in definitions
    assert "event2" in definitions
    assert isinstance(definitions["event1"], EventSubscription)
    assert isinstance(definitions["event2"], EventSubscription)


def test_multi_subscriber_add_subscription(mock_publication: EventPublication) -> None:
    subscriber = MockMultiSubscriber()
    publisher = MockPublisher(mock_publication)

    # Add subscription
    subscriber.add_subscription(subscriber.event1, publisher)

    assert publisher in subscriber.subscribers
    assert subscriber.event1 in subscriber.subscribers[publisher]

    # Test the subscription works
    publisher.trigger_event("test")
    assert len(subscriber.calls) == 1
    assert subscriber.calls[0] == "test"


def test_multi_subscriber_add_duplicate_subscription(
    mock_publication: EventPublication,
) -> None:
    subscriber = MockMultiSubscriber()
    publisher = MockPublisher(mock_publication)

    # Add subscription twice
    subscriber.add_subscription(subscriber.event1, publisher)
    subscriber.add_subscription(subscriber.event1, publisher)

    # Should only be added once
    assert len(subscriber.subscribers[publisher]) == 1


def test_multi_subscriber_add_invalid_subscription(
    mock_publication: EventPublication,
) -> None:
    subscriber = MockMultiSubscriber()
    publisher = MockPublisher(mock_publication)
    invalid_subscription = EventSubscription(
        MockPublisher, MockEvents.EVENT_1, lambda message, tag, publisher: None
    )

    with pytest.raises(
        ValueError, match="Subscription not defined in event definitions"
    ):
        subscriber.add_subscription(invalid_subscription, publisher)


def test_multi_subscriber_remove_subscription(
    mock_publication: EventPublication,
) -> None:
    subscriber = MockMultiSubscriber()
    publisher = MockPublisher(mock_publication)

    # Add and then remove subscription
    subscriber.add_subscription(subscriber.event1, publisher)
    subscriber.remove_subscription(subscriber.event1, publisher)

    assert len(subscriber.subscribers[publisher]) == 0

    # Test the subscription is removed
    publisher.trigger_event("test")
    assert len(subscriber.calls) == 0


def test_multi_subscriber_remove_nonexistent_subscription(
    mock_publication: EventPublication,
) -> None:
    subscriber = MockMultiSubscriber()
    publisher = MockPublisher(mock_publication)

    # Try to remove subscription that wasn't added
    subscriber.remove_subscription(subscriber.event1, publisher)

    # Should not raise any error
    assert len(subscriber.subscribers[publisher]) == 0


def test_multi_subscriber_remove_invalid_subscription(
    mock_publication: EventPublication,
) -> None:
    subscriber = MockMultiSubscriber()
    publisher = MockPublisher(mock_publication)
    invalid_subscription = EventSubscription(
        MockPublisher, MockEvents.EVENT_1, lambda message, tag, publisher: None
    )

    with pytest.raises(
        ValueError, match="Subscription not defined in event definitions"
    ):
        subscriber.remove_subscription(invalid_subscription, publisher)


@pytest.mark.parametrize("log_level", [logging.INFO, logging.WARNING, logging.ERROR])
def test_multi_subscriber_logging_levels(
    log_level: int, caplog: Any, mock_publication: EventPublication
) -> None:
    class LoggingSubscriber(MockMultiSubscriber):
        def handle_event(self, event: Any) -> None:
            self.logger().log(log_level, f"[Test] {event}")
            super().handle_event(event)

        @staticmethod
        def _event_adapter(
            handler: Any,
            subscriber: Any,
            arg: Any,
            current_event_tag: int,
            current_event_caller: EventPublisher,
        ) -> None:
            handler(subscriber, arg)

        # Define event subscription as class attribute
        event1 = EventSubscription(
            MockPublisher, MockEvents.EVENT_1, partial(_event_adapter, handle_event)
        )

    with caplog.at_level(log_level):
        subscriber = LoggingSubscriber()
        publisher = MockPublisher(mock_publication)

        subscriber.add_subscription(subscriber.event1, publisher)
        publisher.trigger_event("test message")

        assert len(caplog.records) >= 1
        assert any("[Test] test message" in record.message for record in caplog.records)


def test_multi_subscriber_logger(caplog: Any) -> None:
    class TestMultiSubscriber(MultiSubscriber):
        def logger(self) -> logging.Logger:
            return logging.getLogger(__name__)

    subscriber = TestMultiSubscriber()
    assert subscriber.logger() == logging.getLogger(__name__)


def test_multi_subscriber_log_event_decorator(caplog: Any) -> None:
    class TestMultiSubscriber(MultiSubscriber):
        def logger(self) -> logging.Logger:
            return logging.getLogger(__name__)

        @MultiSubscriber.log_event(log_level=logging.INFO, log_prefix="TestEvent")
        def handle_event(self, event: Any) -> Any:
            return event

    subscriber = TestMultiSubscriber()
    with caplog.at_level(logging.INFO):
        result = subscriber.handle_event("test_event")
        assert result == "test_event"
        assert "[TestEvent] test_event" in caplog.text


def test_multi_subscriber_log_event_decorator_custom_level(caplog: Any) -> None:
    class TestMultiSubscriber(MultiSubscriber):
        def logger(self) -> logging.Logger:
            return logging.getLogger(__name__)

        @MultiSubscriber.log_event(log_level=logging.WARNING, log_prefix="CustomPrefix")
        def handle_event(self, event: Any) -> Any:
            return event

    subscriber = TestMultiSubscriber()
    with caplog.at_level(logging.WARNING):
        result = subscriber.handle_event("warning_event")
        assert result == "warning_event"
        assert "[CustomPrefix] warning_event" in caplog.text
