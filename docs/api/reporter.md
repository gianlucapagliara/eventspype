# ReportingEventSubscriber

**Module:** `eventspype.sub.reporter`

---

## ReportingEventSubscriber

```python
class ReportingEventSubscriber(EventSubscriber):
    def __init__(self, event_source: str | None = None) -> None
```

A subscriber that logs every received event to Python's `logging` module at `INFO` level. The event is converted to a dict and enriched with metadata before logging.

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_source` | `str \| None` | Optional label added to each log entry as `event_source` |

### Class methods

#### `logger`

```python
@classmethod
def logger(cls) -> logging.Logger
```

Return the shared class-level logger (lazily created).

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

Serialize the event to a dict, add metadata, and log at `INFO` level.

### Serialization strategy

Events are converted to a dict in the following order:

1. **Dataclass** — `dataclasses.asdict(event_object)`
2. **NamedTuple** (any object with `_asdict()`) — `event_object._asdict()`
3. **Fallback** — `{"value": str(event_object)}`

### Metadata added to each log entry

| Key | Value |
|-----|-------|
| `event_name` | `type(event_object).__name__` |
| `event_source` | `self.event_source` |
| `event_tag` | `current_event_tag` (normalized int) |

The full dict is also passed as `extra={"event_data": event_dict}` to support structured logging handlers.

### Example

```python
import logging
from dataclasses import dataclass
from eventspype import EventPublisher, EventPublication, ReportingEventSubscriber

logging.basicConfig(level=logging.INFO)

@dataclass
class MetricEvent:
    name: str
    value: float

pub = EventPublication("metric", MetricEvent)
publisher = EventPublisher(pub)

reporter = ReportingEventSubscriber(event_source="metrics-service")
publisher.add_subscriber(reporter)

publisher.publish(MetricEvent("cpu_usage", 78.3))
# INFO:eventspype.sub.reporter:Event received: {
#   'name': 'cpu_usage', 'value': 78.3,
#   'event_name': 'MetricEvent',
#   'event_source': 'metrics-service',
#   'event_tag': 12345
# }
```
