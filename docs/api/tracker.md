# TrackingEventSubscriber

**Module:** `eventspype.sub.tracker`

---

## TrackingEventSubscriber

```python
class TrackingEventSubscriber(EventSubscriber):
    def __init__(
        self,
        event_source: str | None = None,
        max_len: int = 50,
    ) -> None
```

A subscriber that collects received events and supports async waiting for specific event types. Designed for testing, debugging, and integration scenarios.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `event_source` | `str \| None` | `None` | Optional label identifying the event source |
| `max_len` | `int` | `50` | Maximum events retained in the log; older events are dropped when the deque is full |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `event_log` | `list[Any]` | All collected events as a list |
| `event_source` | `str \| None` | The label passed at construction |

### Methods

#### `call`

```python
def call(
    self,
    event_object: Any,
    current_event_tag: int,
    current_event_caller: Any,
) -> None
```

Invoked by the publisher on each event. Appends the event to the log and notifies any coroutines waiting in `wait_for`.

---

#### `clear`

```python
def clear(self) -> None
```

Empty the event log and any per-type event deques.

---

#### `wait_for`

```python
async def wait_for(
    self, event_type: type[Any], timeout_seconds: float = 180
) -> Any
```

Suspend the current coroutine until an event whose `type` matches `event_type` is received, then return it.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `event_type` | `type` | — | The exact Python class to wait for |
| `timeout_seconds` | `float` | `180` | How long to wait before raising `TimeoutError` |

**Returns:** The matched event object.

**Raises:** `TimeoutError` if no matching event arrives within `timeout_seconds`. Internal state is always cleaned up even if the timeout fires.

### Example

```python
import asyncio
from dataclasses import dataclass
from eventspype import EventPublisher, EventPublication, TrackingEventSubscriber

@dataclass
class AlertEvent:
    level: str
    message: str

pub = EventPublication("alert", AlertEvent)
publisher = EventPublisher(pub)

async def main():
    tracker = TrackingEventSubscriber(event_source="alerts", max_len=100)
    publisher.add_subscriber(tracker)

    # Simulate an event arriving after 0.5 s
    async def trigger():
        await asyncio.sleep(0.5)
        publisher.publish(AlertEvent("ERROR", "Disk full"))

    asyncio.create_task(trigger())

    event = await tracker.wait_for(AlertEvent, timeout_seconds=5)
    print(f"Got alert: [{event.level}] {event.message}")

asyncio.run(main())
```
