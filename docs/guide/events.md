# Events

Events are the data objects that flow through the EventsPype system. This guide explains how to define events, use event tags, and understand how tags are normalized internally.

## Event Types

An event can be **any Python object**. EventsPype does not require a specific base class. Common choices are:

### Dataclasses (recommended)

```python
from dataclasses import dataclass

@dataclass
class OrderPlacedEvent:
    order_id: int
    amount: float
    currency: str = "USD"
```

### Using the `Event` base class

`Event` is an optional marker base class. It adds no behaviour, but it can be useful for type annotations and IDE support:

```python
from eventspype import Event
from dataclasses import dataclass

@dataclass
class OrderPlacedEvent(Event):
    order_id: int
    amount: float
```

### NamedTuples

```python
from typing import NamedTuple

class PriceUpdatedEvent(NamedTuple):
    symbol: str
    price: float
```

### Plain classes

```python
class ConnectionEstablishedEvent:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
```

## Event Tags

An `EventTag` identifies an event channel. Tags are used by `EventPublication` and `EventSubscription` to route events. The type alias is:

```python
EventTag = Enum | int | str
```

### Enum tags (recommended)

```python
from enum import Enum
from eventspype import EventPublication

class OrderEvents(Enum):
    PLACED = 1
    CANCELLED = 2
    FULFILLED = 3

placed_pub = EventPublication(OrderEvents.PLACED, OrderPlacedEvent)
```

### String tags

Strings are hashed deterministically using MD5 so the same string always maps to the same integer across processes and Python restarts:

```python
placed_pub = EventPublication("order_placed", OrderPlacedEvent)
```

!!! note
    String hashing is case-insensitive: `"order_placed"` and `"ORDER_PLACED"` produce the same internal tag.

### Integer tags

```python
placed_pub = EventPublication(1001, OrderPlacedEvent)
```

## Type Validation

When you call `publisher.publish(event)`, EventsPype checks that `event` is an instance of the class declared in the publication. If the types do not match, a `ValueError` is raised:

```python
publication = EventPublication("order_placed", OrderPlacedEvent)
publisher = EventPublisher(publication)

# Raises ValueError: expected OrderPlacedEvent, got PriceUpdatedEvent
publisher.publish(PriceUpdatedEvent(symbol="AAPL", price=150.0))
```

## Accessing Event Information in Subscribers

Subscribers receive three arguments:

| Argument | Type | Description |
|----------|------|-------------|
| `event` | `Any` | The event object |
| `event_tag` | `int` | Normalized integer tag |
| `caller` | `Any` | The publisher that dispatched the event |

```python
from eventspype import EventSubscriber

class DebugSubscriber(EventSubscriber):
    def call(self, event, event_tag, caller):
        print(f"Event type:  {type(event).__name__}")
        print(f"Event tag:   {event_tag}")
        print(f"From:        {caller}")
        print(f"Data:        {event}")
```
