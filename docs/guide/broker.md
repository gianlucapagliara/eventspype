# Message Brokers

A message broker is the transport layer that delivers events from publishers to subscribers. EventsPype ships with two broker implementations and provides a base class for custom brokers.

## Overview

By default, `EventPublisher` dispatches events directly in-process without any broker. Providing a broker changes how events are routed:

```python
from eventspype import EventPublisher, EventPublication, LocalBroker

publication = EventPublication("order_placed", OrderPlacedEvent)

# No broker: in-process, direct dispatch
publisher = EventPublisher(publication)

# With LocalBroker: functionally identical, but routed through the broker
broker = LocalBroker()
publisher = EventPublisher(publication, broker=broker)
```

## MessageBroker (abstract)

`MessageBroker` defines the interface all brokers must implement:

```python
from eventspype import MessageBroker

class MessageBroker:
    def publish(self, channel: str, event, event_tag: int, caller) -> None: ...
    def subscribe(self, channel: str, subscriber) -> None: ...
    def unsubscribe(self, channel: str, subscriber) -> None: ...
```

The `channel` string is derived from the publication's event tag (`str(publication.event_tag)`).

## LocalBroker

`LocalBroker` is an in-process broker that uses weak references, matching the default behavior of `EventPublisher` without a broker:

```python
from eventspype import LocalBroker

broker = LocalBroker()
publisher = EventPublisher(publication, broker=broker)
```

Use `LocalBroker` when you want to decouple the transport layer from your publisher while keeping everything in the same process.

## RedisBroker

`RedisBroker` routes events through Redis Pub/Sub, enabling cross-process event delivery. It requires the `redis` package:

```bash
pip install redis
```

### Basic usage

```python
import redis
from eventspype.broker.redis import RedisBroker
from eventspype import EventPublisher, EventPublication

client = redis.Redis(host="localhost", port=6379)
broker = RedisBroker(client)

publication = EventPublication("order_placed", OrderPlacedEvent)
publisher = EventPublisher(publication, broker=broker)

# Publish an event — it is serialized and sent to Redis
publisher.publish(OrderPlacedEvent(order_id=1, amount=49.99))

# Clean up Redis resources when done
broker.close()
```

### How it works

1. On `publish`, the event is serialized and sent to a Redis channel named `eventspype:<tag>`.
2. A background listener thread receives messages from Redis and deserializes them back into event objects.
3. The deserialized event is dispatched to all registered local subscribers.

### Channel prefix

The default channel prefix is `"eventspype:"`. Override it:

```python
broker = RedisBroker(client, channel_prefix="myapp:")
```

### Custom serializer

`RedisBroker` defaults to `JsonEventSerializer`. Provide a custom serializer by subclassing `EventSerializer`:

```python
from eventspype import EventSerializer, JsonEventSerializer

class MySerializer(EventSerializer):
    def serialize(self, event) -> bytes:
        ...

    def deserialize(self, data: bytes, event_class: type):
        ...

broker = RedisBroker(client, serializer=MySerializer())
```

## EventSerializer

`EventSerializer` is the abstract base for event serialization used by `RedisBroker`:

```python
class EventSerializer:
    def serialize(self, event) -> bytes: ...
    def deserialize(self, data: bytes, event_class: type): ...
```

### JsonEventSerializer

`JsonEventSerializer` supports dataclasses, NamedTuples, and objects with a `to_dict()`/`from_dict()` protocol:

```python
from eventspype import JsonEventSerializer

serializer = JsonEventSerializer()
data = serializer.serialize(OrderPlacedEvent(order_id=1, amount=49.99))
event = serializer.deserialize(data, OrderPlacedEvent)
```

## Swapping Brokers at Runtime

You can change a publisher's broker after construction. The publisher automatically migrates existing subscribers to the new broker:

```python
publisher.broker = new_broker  # old broker unsubscribes; new broker subscribes

publisher.broker = None        # revert to direct in-process dispatch
```

## Writing a Custom Broker

Subclass `MessageBroker` and implement the three abstract methods:

```python
from eventspype import MessageBroker
from eventspype.sub.subscriber import EventSubscriber

class MyBroker(MessageBroker):
    def publish(self, channel: str, event, event_tag: int, caller) -> None:
        # Deliver the event
        ...

    def subscribe(self, channel: str, subscriber: EventSubscriber) -> None:
        # Register the subscriber for the channel
        ...

    def unsubscribe(self, channel: str, subscriber: EventSubscriber) -> None:
        # Remove the subscriber from the channel
        ...
```
