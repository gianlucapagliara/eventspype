# Brokers

**Module:** `eventspype.broker`

---

## MessageBroker

**Module:** `eventspype.broker.broker`

```python
class MessageBroker
```

Abstract base class for message brokers. All broker implementations must subclass `MessageBroker` and implement the three abstract methods.

### Abstract methods

#### `publish`

```python
@abstractmethod
def publish(self, channel: str, event: Any, event_tag: int, caller: Any) -> None
```

Deliver an event to a channel.

| Parameter | Type | Description |
|-----------|------|-------------|
| `channel` | `str` | Channel name (derived from the publication tag) |
| `event` | `Any` | The event object |
| `event_tag` | `int` | Normalized integer tag |
| `caller` | `Any` | The publisher that triggered the event |

---

#### `subscribe`

```python
@abstractmethod
def subscribe(self, channel: str, subscriber: EventSubscriber) -> None
```

Register a subscriber for a channel.

---

#### `unsubscribe`

```python
@abstractmethod
def unsubscribe(self, channel: str, subscriber: EventSubscriber) -> None
```

Remove a subscriber from a channel.

---

## LocalBroker

**Module:** `eventspype.broker.local`

```python
class LocalBroker(MessageBroker):
    def __init__(self) -> None
```

In-process broker that dispatches events directly to subscribers using weak references. Functionally equivalent to `EventPublisher` without a broker, but useful when you want a pluggable transport layer in the same process.

### Methods

All three abstract methods are implemented. Dead subscriber references are cleaned up on each `publish` and `unsubscribe` call.

### Example

```python
from eventspype import LocalBroker, EventPublisher, EventPublication

broker = LocalBroker()
pub = EventPublication("my_event", MyEvent)
publisher = EventPublisher(pub, broker=broker)
```

---

## RedisBroker

**Module:** `eventspype.broker.redis`

```python
class RedisBroker(MessageBroker):
    def __init__(
        self,
        redis_client: Any,
        serializer: EventSerializer | None = None,
        channel_prefix: str = "eventspype:",
    ) -> None
```

Cross-process broker using Redis Pub/Sub. Requires `pip install redis`.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `redis_client` | `redis.Redis` | — | Connected Redis client |
| `serializer` | `EventSerializer \| None` | `None` | Serializer for events. Defaults to `JsonEventSerializer`. |
| `channel_prefix` | `str` | `"eventspype:"` | Prefix added to all Redis channel names |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `logger` | `logging.Logger` | Logger instance (lazily created) |

### Methods

In addition to the three abstract methods:

#### `close`

```python
def close(self) -> None
```

Unsubscribe from all Redis channels, close the pubsub connection, and stop the listener thread.

### How it works

1. On `subscribe`, a Redis pubsub channel is created and a background listener thread is started via `run_in_thread`.
2. On `publish`, the event is serialized to JSON and published to `{channel_prefix}{channel}`.
3. The listener thread receives messages, deserializes the event class from the message metadata, deserializes the payload, and dispatches to all registered local subscribers.

### Example

```python
import redis
from eventspype.broker.redis import RedisBroker
from eventspype import EventPublisher, EventPublication
from dataclasses import dataclass

@dataclass
class TradeEvent:
    symbol: str
    price: float

client = redis.Redis(host="localhost", port=6379)
broker = RedisBroker(client, channel_prefix="trading:")

pub = EventPublication("trade", TradeEvent)
publisher = EventPublisher(pub, broker=broker)

publisher.publish(TradeEvent("AAPL", 155.0))

broker.close()
```

---

## EventSerializer

**Module:** `eventspype.broker.serializer`

```python
class EventSerializer
```

Abstract base class for event serialization used by `RedisBroker`.

### Abstract methods

#### `serialize`

```python
@abstractmethod
def serialize(self, event: Any) -> bytes
```

Convert an event object to bytes.

---

#### `deserialize`

```python
@abstractmethod
def deserialize(self, data: bytes, event_class: type) -> Any
```

Reconstruct an event object from bytes and its class.

---

## JsonEventSerializer

**Module:** `eventspype.broker.serializer`

```python
class JsonEventSerializer(EventSerializer)
```

JSON-based serializer. Supports dataclasses, NamedTuples, and objects with `to_dict()`/`from_dict()` methods.

### Serialization strategy

**Serialize:**

1. Dataclass → `dataclasses.asdict(event)` → JSON
2. NamedTuple (has `_asdict`) → `event._asdict()` → JSON
3. Has `to_dict()` → `event.to_dict()` → JSON
4. Fallback → JSON-encode the value directly

**Deserialize:**

1. Dataclass → `event_class(**data)`
2. NamedTuple (has `_make`) → `event_class(**data)`
3. Has `from_dict()` → `event_class.from_dict(data)`
4. Fallback → return raw parsed value

### Example

```python
from eventspype import JsonEventSerializer
from dataclasses import dataclass

@dataclass
class PriceEvent:
    symbol: str
    price: float

serializer = JsonEventSerializer()
data = serializer.serialize(PriceEvent("GOOG", 2800.0))
event = serializer.deserialize(data, PriceEvent)
assert event == PriceEvent("GOOG", 2800.0)
```
