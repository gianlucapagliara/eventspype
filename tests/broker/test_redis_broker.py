import json
import logging
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest

from eventspype.broker.redis import RedisBroker
from eventspype.broker.serializer import JsonEventSerializer
from eventspype.sub.subscriber import EventSubscriber


@dataclass
class SampleEvent:
    message: str


@dataclass
class AnotherEvent:
    value: int


class MockSubscriber(EventSubscriber):
    def __init__(self) -> None:
        self.received_messages: list[Any] = []
        self.received_tags: list[int] = []
        self.received_callers: list[Any] = []

    def call(self, arg: Any, current_event_tag: int, current_event_caller: Any) -> None:
        self.received_messages.append(arg)
        self.received_tags.append(current_event_tag)
        self.received_callers.append(current_event_caller)


class ErrorSubscriber(EventSubscriber):
    def call(self, arg: Any, current_event_tag: int, current_event_caller: Any) -> None:
        raise ValueError("subscriber boom")


@pytest.fixture
def mock_redis() -> MagicMock:
    client = MagicMock()
    pubsub = MagicMock()
    client.pubsub.return_value = pubsub
    thread = MagicMock()
    thread.is_alive.return_value = True
    pubsub.run_in_thread.return_value = thread
    return client


@pytest.fixture
def broker(mock_redis: MagicMock) -> RedisBroker:
    return RedisBroker(mock_redis)


@pytest.fixture
def subscriber() -> MockSubscriber:
    return MockSubscriber()


# --- __init__ tests ---


def test_init_defaults(mock_redis: MagicMock) -> None:
    broker = RedisBroker(mock_redis)
    assert broker._redis is mock_redis
    assert isinstance(broker._serializer, JsonEventSerializer)
    assert broker._channel_prefix == "eventspype:"
    assert broker._pubsub is None
    assert broker._subscribers == {}
    assert broker._listener_thread is None
    assert broker._logger is None


def test_init_custom_serializer_and_prefix(mock_redis: MagicMock) -> None:
    custom_serializer = MagicMock()
    broker = RedisBroker(
        mock_redis, serializer=custom_serializer, channel_prefix="custom:"
    )
    assert broker._serializer is custom_serializer
    assert broker._channel_prefix == "custom:"


# --- logger property tests ---


def test_logger_lazy_init(broker: RedisBroker) -> None:
    assert broker._logger is None
    logger = broker.logger
    assert logger is not None
    assert isinstance(logger, logging.Logger)


def test_logger_cached(broker: RedisBroker) -> None:
    logger1 = broker.logger
    logger2 = broker.logger
    assert logger1 is logger2


# --- _prefixed_channel tests ---


def test_prefixed_channel_default(broker: RedisBroker) -> None:
    assert broker._prefixed_channel("events") == "eventspype:events"


def test_prefixed_channel_custom_prefix(mock_redis: MagicMock) -> None:
    broker = RedisBroker(mock_redis, channel_prefix="app:")
    assert broker._prefixed_channel("test") == "app:test"


# --- publish tests ---


def test_publish_serializes_and_sends(
    broker: RedisBroker, mock_redis: MagicMock
) -> None:
    event = SampleEvent(message="hello")
    broker.publish("chan", event, 42, None)

    mock_redis.publish.assert_called_once()
    call_args = mock_redis.publish.call_args
    assert call_args[0][0] == "eventspype:chan"

    payload = json.loads(call_args[0][1])
    assert payload["event_tag"] == 42
    assert payload["event_class"] == "SampleEvent"
    assert payload["event_module"] == __name__
    assert "message" in payload["payload"]


def test_publish_uses_custom_serializer(mock_redis: MagicMock) -> None:
    serializer = MagicMock()
    serializer.serialize.return_value = b'{"message": "hi"}'
    broker = RedisBroker(mock_redis, serializer=serializer)

    event = SampleEvent(message="hi")
    broker.publish("chan", event, 1, None)

    serializer.serialize.assert_called_once_with(event)
    mock_redis.publish.assert_called_once()


# --- subscribe tests ---


def test_subscribe_creates_pubsub_on_first_channel(
    broker: RedisBroker, mock_redis: MagicMock, subscriber: MockSubscriber
) -> None:
    broker.subscribe("chan1", subscriber)

    mock_redis.pubsub.assert_called_once()
    pubsub = mock_redis.pubsub.return_value
    pubsub.subscribe.assert_called_once()
    # Check the keyword arg is the prefixed channel
    call_kwargs = pubsub.subscribe.call_args[1]
    assert "eventspype:chan1" in call_kwargs


def test_subscribe_reuses_pubsub_for_same_channel(
    broker: RedisBroker, mock_redis: MagicMock
) -> None:
    sub1 = MockSubscriber()
    sub2 = MockSubscriber()
    broker.subscribe("chan1", sub1)
    broker.subscribe("chan1", sub2)

    # pubsub.subscribe called only once for the channel
    pubsub = mock_redis.pubsub.return_value
    assert pubsub.subscribe.call_count == 1
    assert len(broker._subscribers["chan1"]) == 2


def test_subscribe_new_channel_subscribes_again(
    broker: RedisBroker, mock_redis: MagicMock
) -> None:
    sub1 = MockSubscriber()
    sub2 = MockSubscriber()
    broker.subscribe("chan1", sub1)
    broker.subscribe("chan2", sub2)

    pubsub = mock_redis.pubsub.return_value
    assert pubsub.subscribe.call_count == 2


def test_subscribe_starts_listener(
    broker: RedisBroker, mock_redis: MagicMock, subscriber: MockSubscriber
) -> None:
    broker.subscribe("chan1", subscriber)

    pubsub = mock_redis.pubsub.return_value
    pubsub.run_in_thread.assert_called_once_with(sleep_time=0.01, daemon=True)


# --- unsubscribe tests ---


def test_unsubscribe_nonexistent_channel(
    broker: RedisBroker, subscriber: MockSubscriber
) -> None:
    # Should not raise
    broker.unsubscribe("nonexistent", subscriber)


def test_unsubscribe_removes_subscriber(
    broker: RedisBroker, mock_redis: MagicMock
) -> None:
    sub1 = MockSubscriber()
    sub2 = MockSubscriber()
    broker.subscribe("chan1", sub1)
    broker.subscribe("chan1", sub2)

    broker.unsubscribe("chan1", sub1)
    assert len(broker._subscribers["chan1"]) == 1
    assert broker._subscribers["chan1"][0] is sub2


def test_unsubscribe_last_subscriber_removes_channel(
    broker: RedisBroker, mock_redis: MagicMock, subscriber: MockSubscriber
) -> None:
    broker.subscribe("chan1", subscriber)
    broker.unsubscribe("chan1", subscriber)

    assert "chan1" not in broker._subscribers
    pubsub = mock_redis.pubsub.return_value
    pubsub.unsubscribe.assert_called_once_with("eventspype:chan1")


def test_unsubscribe_last_subscriber_when_pubsub_none(
    mock_redis: MagicMock, subscriber: MockSubscriber
) -> None:
    broker = RedisBroker(mock_redis)
    # Manually set up state without pubsub
    broker._subscribers["chan1"] = [subscriber]
    broker.unsubscribe("chan1", subscriber)

    assert "chan1" not in broker._subscribers
    # pubsub was None, so no unsubscribe call on it
    mock_redis.pubsub.return_value.unsubscribe.assert_not_called()


# --- close tests ---


def test_close_cleans_up_pubsub(
    broker: RedisBroker, mock_redis: MagicMock, subscriber: MockSubscriber
) -> None:
    broker.subscribe("chan1", subscriber)
    pubsub = mock_redis.pubsub.return_value

    broker.close()

    pubsub.unsubscribe.assert_called()
    pubsub.close.assert_called_once()
    assert broker._pubsub is None
    assert broker._listener_thread is None


def test_close_when_pubsub_is_none(broker: RedisBroker) -> None:
    # Should not raise
    broker.close()
    assert broker._pubsub is None
    assert broker._listener_thread is None


# --- _ensure_pubsub tests ---


def test_ensure_pubsub_creates_once(broker: RedisBroker, mock_redis: MagicMock) -> None:
    broker._ensure_pubsub()
    broker._ensure_pubsub()

    mock_redis.pubsub.assert_called_once()
    assert broker._pubsub is mock_redis.pubsub.return_value


# --- _ensure_listener tests ---


def test_ensure_listener_creates_thread(
    broker: RedisBroker, mock_redis: MagicMock
) -> None:
    broker._ensure_pubsub()
    pubsub = mock_redis.pubsub.return_value
    broker._ensure_listener()

    pubsub.run_in_thread.assert_called_once_with(sleep_time=0.01, daemon=True)
    assert broker._listener_thread is pubsub.run_in_thread.return_value


def test_ensure_listener_restarts_dead_thread(
    broker: RedisBroker, mock_redis: MagicMock
) -> None:
    broker._ensure_pubsub()
    pubsub = mock_redis.pubsub.return_value

    # First call creates thread
    dead_thread = MagicMock()
    dead_thread.is_alive.return_value = False
    pubsub.run_in_thread.return_value = dead_thread
    broker._ensure_listener()

    # Thread is dead, so next call should create a new one
    new_thread = MagicMock()
    new_thread.is_alive.return_value = True
    pubsub.run_in_thread.return_value = new_thread
    broker._ensure_listener()

    assert pubsub.run_in_thread.call_count == 2
    assert broker._listener_thread is new_thread


def test_ensure_listener_skips_if_alive(
    broker: RedisBroker, mock_redis: MagicMock
) -> None:
    broker._ensure_pubsub()
    pubsub = mock_redis.pubsub.return_value

    alive_thread = MagicMock()
    alive_thread.is_alive.return_value = True
    pubsub.run_in_thread.return_value = alive_thread
    broker._ensure_listener()
    broker._ensure_listener()

    # Only created once since thread is alive
    assert pubsub.run_in_thread.call_count == 1


# --- _make_handler tests ---


def test_handler_skips_non_message_type(broker: RedisBroker) -> None:
    handler = broker._make_handler("chan1")
    # Should not raise for non-message types
    handler({"type": "subscribe", "data": 1})
    handler({"type": "unsubscribe", "data": 0})


def test_handler_dispatches_event_to_subscribers(
    broker: RedisBroker, subscriber: MockSubscriber
) -> None:
    broker._subscribers["chan1"] = [subscriber]
    handler = broker._make_handler("chan1")

    event = SampleEvent(message="test")
    serializer = JsonEventSerializer()
    payload = serializer.serialize(event).decode("utf-8")

    message = {
        "type": "message",
        "data": json.dumps(
            {
                "event_tag": 7,
                "event_class": "SampleEvent",
                "event_module": __name__,
                "payload": payload,
            }
        ),
    }
    handler(message)

    assert len(subscriber.received_messages) == 1
    assert subscriber.received_messages[0] == SampleEvent(message="test")
    assert subscriber.received_tags[0] == 7


def test_handler_dispatches_to_multiple_subscribers(broker: RedisBroker) -> None:
    sub1 = MockSubscriber()
    sub2 = MockSubscriber()
    broker._subscribers["chan1"] = [sub1, sub2]
    handler = broker._make_handler("chan1")

    event = SampleEvent(message="multi")
    serializer = JsonEventSerializer()
    payload = serializer.serialize(event).decode("utf-8")

    message = {
        "type": "message",
        "data": json.dumps(
            {
                "event_tag": 1,
                "event_class": "SampleEvent",
                "event_module": __name__,
                "payload": payload,
            }
        ),
    }
    handler(message)

    assert len(sub1.received_messages) == 1
    assert len(sub2.received_messages) == 1


def test_handler_catches_subscriber_error(broker: RedisBroker, caplog: Any) -> None:
    error_sub = ErrorSubscriber()
    broker._subscribers["chan1"] = [error_sub]
    handler = broker._make_handler("chan1")

    event = SampleEvent(message="fail")
    serializer = JsonEventSerializer()
    payload = serializer.serialize(event).decode("utf-8")

    message = {
        "type": "message",
        "data": json.dumps(
            {
                "event_tag": 1,
                "event_class": "SampleEvent",
                "event_module": __name__,
                "payload": payload,
            }
        ),
    }

    with caplog.at_level(logging.ERROR):
        handler(message)

    assert any(
        "Error dispatching event on channel chan1" in r.message for r in caplog.records
    )


def test_handler_continues_after_subscriber_error(broker: RedisBroker) -> None:
    """Verify that an error in one subscriber doesn't prevent others from receiving the event."""
    error_sub = ErrorSubscriber()
    good_sub = MockSubscriber()
    broker._subscribers["chan1"] = [error_sub, good_sub]
    handler = broker._make_handler("chan1")

    event = SampleEvent(message="partial")
    serializer = JsonEventSerializer()
    payload = serializer.serialize(event).decode("utf-8")

    message = {
        "type": "message",
        "data": json.dumps(
            {
                "event_tag": 1,
                "event_class": "SampleEvent",
                "event_module": __name__,
                "payload": payload,
            }
        ),
    }
    handler(message)

    assert len(good_sub.received_messages) == 1


def test_handler_catches_deserialization_error(
    broker: RedisBroker, caplog: Any
) -> None:
    handler = broker._make_handler("chan1")

    message = {
        "type": "message",
        "data": "not valid json {{{",
    }

    with caplog.at_level(logging.ERROR):
        handler(message)

    assert any(
        "Error processing Redis message on channel chan1" in r.message
        for r in caplog.records
    )


def test_handler_catches_bad_module_error(broker: RedisBroker, caplog: Any) -> None:
    handler = broker._make_handler("chan1")

    message = {
        "type": "message",
        "data": json.dumps(
            {
                "event_tag": 1,
                "event_class": "NonExistentClass",
                "event_module": "nonexistent.module.that.does.not.exist",
                "payload": "{}",
            }
        ),
    }

    with caplog.at_level(logging.ERROR):
        handler(message)

    assert any(
        "Error processing Redis message on channel chan1" in r.message
        for r in caplog.records
    )


# --- _resolve_class tests ---


def test_resolve_class_dataclass(broker: RedisBroker) -> None:
    cls = broker._resolve_class(__name__, "SampleEvent")
    assert cls is SampleEvent


def test_resolve_class_builtin(broker: RedisBroker) -> None:
    cls = broker._resolve_class("builtins", "dict")
    assert cls is dict


def test_resolve_class_nested(broker: RedisBroker) -> None:
    cls = broker._resolve_class("json", "JSONEncoder")
    import json as json_mod

    assert cls is json_mod.JSONEncoder


def test_resolve_class_invalid_module(broker: RedisBroker) -> None:
    with pytest.raises(ModuleNotFoundError):
        broker._resolve_class("nonexistent_module_xyz", "Foo")


def test_resolve_class_invalid_attr(broker: RedisBroker) -> None:
    with pytest.raises(AttributeError):
        broker._resolve_class(__name__, "ClassThatDoesNotExist")


# --- Integration-style test ---


def test_publish_subscribe_roundtrip(mock_redis: MagicMock) -> None:
    """Simulate a full publish-subscribe cycle by capturing the handler and invoking it."""
    broker = RedisBroker(mock_redis)
    subscriber = MockSubscriber()

    broker.subscribe("events", subscriber)

    # Capture the handler that was registered with pubsub.subscribe
    pubsub = mock_redis.pubsub.return_value
    call_kwargs = pubsub.subscribe.call_args[1]
    handler = call_kwargs["eventspype:events"]

    # Now publish an event
    event = SampleEvent(message="roundtrip")
    broker.publish("events", event, 99, None)

    # Get the message that was published
    publish_call = mock_redis.publish.call_args
    published_data = publish_call[0][1]

    # Feed it back through the handler as Redis would
    handler({"type": "message", "data": published_data})

    assert len(subscriber.received_messages) == 1
    assert subscriber.received_messages[0] == SampleEvent(message="roundtrip")
    assert subscriber.received_tags[0] == 99
