# EventPublisher

**Module:** `eventspype.pub.publisher`

---

## EventPublisher

```python
class EventPublisher:
    def __init__(
        self,
        publication: EventPublication,
        broker: MessageBroker | None = None,
    ) -> None
```

Single-publication publisher. Holds a set of weak references to subscribers and dispatches events to all live ones.

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `publication` | `EventPublication` | The publication this publisher manages |
| `broker` | `MessageBroker \| None` | Optional broker for external dispatch. Defaults to `None` (direct in-process dispatch). |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Class name of the publisher |
| `logger` | `logging.Logger` | Logger instance (lazily created) |
| `broker` | `MessageBroker \| None` | Current broker. Settable; migrates subscribers when changed. |

### Methods

#### `add_subscriber`

```python
def add_subscriber(self, subscriber: EventSubscriber) -> None
```

Register a subscriber. Stored as a weak reference. Periodically triggers garbage collection of dead references (probability 0.005 per call).

---

#### `remove_subscriber`

```python
def remove_subscriber(self, subscriber: EventSubscriber) -> None
```

Unregister a subscriber and clean up dead references.

---

#### `get_subscribers`

```python
def get_subscribers(self) -> list[EventSubscriber]
```

Return a list of all currently live subscribers. Dead references are removed before returning.

---

#### `publish`

```python
def publish(self, event: Any, caller: Any | None = None) -> None
```

Dispatch an event to all live subscribers.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `event` | `Any` | The event object to dispatch |
| `caller` | `Any \| None` | Override the caller passed to subscribers. Defaults to `self`. |

**Raises:** `ValueError` if `event` is not an instance of `publication.event_class`.

When a broker is set, the event is serialized and routed through the broker. Otherwise events are dispatched directly in-process.

Exceptions raised inside subscriber `call()` methods are caught and logged; they do not interrupt delivery to other subscribers.

### Class attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `ADD_SUBSCRIBER_GC_PROBABILITY` | `float` | Probability of running GC on each `add_subscriber` call. Default: `0.005`. |

### Example

```python
from dataclasses import dataclass
from eventspype import EventPublisher, EventPublication, EventSubscriber

@dataclass
class TemperatureEvent:
    sensor_id: str
    celsius: float

pub = EventPublication("temperature", TemperatureEvent)
publisher = EventPublisher(pub)

class TempLogger(EventSubscriber):
    def call(self, event, event_tag, caller):
        print(f"{event.sensor_id}: {event.celsius}°C")

logger = TempLogger()
publisher.add_subscriber(logger)
publisher.publish(TemperatureEvent("sensor-1", 22.5))
# sensor-1: 22.5°C
```
