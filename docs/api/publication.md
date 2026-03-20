# EventPublication

**Module:** `eventspype.pub.publication`

---

## EventPublication

```python
class EventPublication:
    def __init__(self, event_tag: EventTag, event_class: Any) -> None
```

Describes a single event channel: the tag that identifies it and the Python class that events must be instances of.

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_tag` | `EventTag` | Tag identifying this publication. Accepts `Enum`, `int`, or `str`. |
| `event_class` | `type` | The expected event class. `EventPublisher.publish()` validates events against this. |

### Tag normalization

| Input type | Stored as |
|-----------|-----------|
| `Enum` | `int` via `enum.value` |
| `int` | unchanged |
| `str` | deterministic MD5 hash (case-insensitive) |

Passing any other type raises `ValueError`.

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `original_tag` | `EventTag` | The tag as passed to `__init__` (before normalization) |
| `event_tag` | `int` | The normalized integer tag used internally |
| `event_class` | `type` | The event class |

### Hashing

`EventPublication` is hashable. Two publications with the same normalized `event_tag` are considered equal in a hash set/dict.

### Example

```python
from enum import Enum
from dataclasses import dataclass
from eventspype import EventPublication

class OrderEvents(Enum):
    PLACED = 1
    CANCELLED = 2

@dataclass
class OrderPlacedEvent:
    order_id: int
    amount: float

# Using an Enum tag
placed = EventPublication(OrderEvents.PLACED, OrderPlacedEvent)

# Using a string tag
placed_str = EventPublication("order_placed", OrderPlacedEvent)

# Using an integer tag
placed_int = EventPublication(1, OrderPlacedEvent)
```
