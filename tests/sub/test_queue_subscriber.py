import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any

import pytest

from eventspype.pub.publication import EventPublication
from eventspype.pub.publisher import EventPublisher
from eventspype.sub.queue import QueueEventSubscriber


class MockTag(Enum):
    TEST = 1


@dataclass
class SampleEvent:
    value: int
    label: str


class CallerWithName:
    name = "my_caller"


class CallerWithoutName:
    pass


@pytest.fixture
def subscriber() -> QueueEventSubscriber:
    return QueueEventSubscriber(max_queue_size=1000)


class TestSubscribeUnsubscribe:
    def test_subscribe_returns_queue_with_correct_maxsize(
        self, subscriber: QueueEventSubscriber
    ) -> None:
        queue = subscriber.subscribe_consumer()
        assert isinstance(queue, asyncio.Queue)
        assert queue.maxsize == 1000

    def test_unsubscribe_removes_queue(self, subscriber: QueueEventSubscriber) -> None:
        queue = subscriber.subscribe_consumer()
        assert subscriber.consumer_count == 1
        subscriber.unsubscribe_consumer(queue)
        assert subscriber.consumer_count == 0

    def test_unsubscribe_unknown_queue_is_noop(
        self, subscriber: QueueEventSubscriber
    ) -> None:
        unknown: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        subscriber.unsubscribe_consumer(unknown)  # should not raise
        assert subscriber.consumer_count == 0

    def test_consumer_count(self, subscriber: QueueEventSubscriber) -> None:
        q1 = subscriber.subscribe_consumer()
        q2 = subscriber.subscribe_consumer()
        assert subscriber.consumer_count == 2
        subscriber.unsubscribe_consumer(q1)
        assert subscriber.consumer_count == 1
        subscriber.unsubscribe_consumer(q2)
        assert subscriber.consumer_count == 0


class TestCall:
    def test_fans_out_to_all_queues(self, subscriber: QueueEventSubscriber) -> None:
        q1 = subscriber.subscribe_consumer()
        q2 = subscriber.subscribe_consumer()

        event = SampleEvent(value=42, label="test")
        subscriber.call(event, MockTag.TEST.value, CallerWithName())

        assert not q1.empty()
        assert not q2.empty()
        d1 = q1.get_nowait()
        d2 = q2.get_nowait()
        assert d1["data"] == d2["data"]

    def test_no_consumers_is_noop(self, subscriber: QueueEventSubscriber) -> None:
        event = SampleEvent(value=1, label="x")
        # Should not raise
        subscriber.call(event, 1, CallerWithName())

    def test_event_dict_structure(self, subscriber: QueueEventSubscriber) -> None:
        queue = subscriber.subscribe_consumer()
        event = SampleEvent(value=10, label="hello")
        subscriber.call(event, 99, CallerWithName())

        result = queue.get_nowait()
        assert result["event_type"] == "SampleEvent"
        assert result["event_tag"] == 99
        assert result["caller"] == "my_caller"
        assert isinstance(result["timestamp"], float)
        assert result["data"] == {"value": 10, "label": "hello"}

    def test_dataclass_event_serialized(self, subscriber: QueueEventSubscriber) -> None:
        queue = subscriber.subscribe_consumer()
        event = SampleEvent(value=5, label="dc")
        subscriber.call(event, 1, CallerWithName())

        result = queue.get_nowait()
        assert result["data"] == {"value": 5, "label": "dc"}

    def test_full_queue_silently_skipped(self) -> None:
        sub = QueueEventSubscriber(max_queue_size=1)
        queue = sub.subscribe_consumer()

        event = SampleEvent(value=1, label="a")
        sub.call(event, 1, CallerWithName())
        sub.call(event, 1, CallerWithName())  # queue is full, should not raise

        assert queue.qsize() == 1

    def test_caller_name_from_name_attribute(
        self, subscriber: QueueEventSubscriber
    ) -> None:
        queue = subscriber.subscribe_consumer()
        subscriber.call(SampleEvent(1, "x"), 1, CallerWithName())
        result = queue.get_nowait()
        assert result["caller"] == "my_caller"

    def test_caller_name_fallback_to_class_name(
        self, subscriber: QueueEventSubscriber
    ) -> None:
        queue = subscriber.subscribe_consumer()
        subscriber.call(SampleEvent(1, "x"), 1, CallerWithoutName())
        result = queue.get_nowait()
        assert result["caller"] == "CallerWithoutName"


class TestIntegrationWithPublisher:
    def test_publish_arrives_in_queue(self) -> None:
        """Wire QueueEventSubscriber to EventPublisher and verify delivery.

        Important: we keep a strong reference to the subscriber because
        EventPublisher holds only a weak reference.
        """
        pub = EventPublication(event_tag=MockTag.TEST, event_class=SampleEvent)
        publisher = EventPublisher(publication=pub)

        subscriber = QueueEventSubscriber()  # strong ref kept here
        publisher.add_subscriber(subscriber)

        queue = subscriber.subscribe_consumer()

        event = SampleEvent(value=77, label="integration")
        publisher.publish(event)

        assert not queue.empty()
        result = queue.get_nowait()
        assert result["event_type"] == "SampleEvent"
        assert result["data"] == {"value": 77, "label": "integration"}

    def test_weak_ref_without_strong_ref(self) -> None:
        """Without a strong reference the subscriber is garbage-collected."""
        pub = EventPublication(event_tag=MockTag.TEST, event_class=SampleEvent)
        publisher = EventPublisher(publication=pub)

        subscriber = QueueEventSubscriber()
        publisher.add_subscriber(subscriber)
        assert len(publisher.get_subscribers()) == 1

        # Drop strong reference
        del subscriber

        # Subscriber should have been collected
        assert len(publisher.get_subscribers()) == 0
