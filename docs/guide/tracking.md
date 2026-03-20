# Event Tracking and Reporting

EventsPype includes two built-in subscriber types for observing events without altering your business logic: `TrackingEventSubscriber` for collection and async waiting, and `ReportingEventSubscriber` for structured logging.

## TrackingEventSubscriber

`TrackingEventSubscriber` is designed for testing, debugging, and any scenario where you need to inspect events after the fact or wait for them asynchronously.

### Basic usage

```python
from eventspype import EventPublisher, EventPublication, TrackingEventSubscriber
from dataclasses import dataclass

@dataclass
class PriceUpdatedEvent:
    symbol: str
    price: float

publication = EventPublication("price_updated", PriceUpdatedEvent)
publisher = EventPublisher(publication)

tracker = TrackingEventSubscriber(event_source="market-feed", max_len=200)
publisher.add_subscriber(tracker)

publisher.publish(PriceUpdatedEvent("AAPL", 150.0))
publisher.publish(PriceUpdatedEvent("GOOG", 2800.0))

print(tracker.event_log)
# [PriceUpdatedEvent(symbol='AAPL', price=150.0),
#  PriceUpdatedEvent(symbol='GOOG', price=2800.0)]
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `event_source` | `str \| None` | `None` | Optional label for identifying the event source |
| `max_len` | `int` | `50` | Maximum events to retain in the log (older events are dropped) |

### Properties

```python
tracker.event_log     # list[Any] — all collected events
tracker.event_source  # str | None — the label passed at construction
```

### Clearing events

```python
tracker.clear()  # empties the event log
```

### Async waiting

`wait_for` suspends the current coroutine until an event of the specified type arrives:

```python
import asyncio
from eventspype import TrackingEventSubscriber

async def main():
    tracker = TrackingEventSubscriber()
    publisher.add_subscriber(tracker)

    # Trigger the event somewhere (e.g. another task)
    asyncio.get_event_loop().call_later(
        1.0, publisher.publish, PriceUpdatedEvent("AAPL", 155.0)
    )

    # Wait for it
    event = await tracker.wait_for(PriceUpdatedEvent, timeout_seconds=5)
    print(f"Received: {event}")

asyncio.run(main())
```

If the event does not arrive within `timeout_seconds` (default: 180), `TimeoutError` is raised. Internal state is always cleaned up, even on timeout.

### Using in tests

```python
import pytest
from eventspype import TrackingEventSubscriber

def test_event_published():
    tracker = TrackingEventSubscriber()
    publisher.add_subscriber(tracker)

    publisher.publish(PriceUpdatedEvent("AAPL", 150.0))

    assert len(tracker.event_log) == 1
    assert tracker.event_log[0].symbol == "AAPL"
```

## ReportingEventSubscriber

`ReportingEventSubscriber` logs every received event at `INFO` level using Python's `logging` module. It automatically converts the event to a dict and attaches metadata.

### Basic usage

```python
import logging
from eventspype import ReportingEventSubscriber

logging.basicConfig(level=logging.INFO)

reporter = ReportingEventSubscriber(event_source="order-service")
publisher.add_subscriber(reporter)

publisher.publish(OrderPlacedEvent(order_id=1, amount=49.99))
# INFO: Event received: {'order_id': 1, 'amount': 49.99,
#                         'event_name': 'OrderPlacedEvent',
#                         'event_source': 'order-service', 'event_tag': 12345}
```

### Supported event types

The reporter serializes the event to a dict using the following strategy (in order):

1. **Dataclass** — uses `dataclasses.asdict()`
2. **NamedTuple** — uses `event._asdict()`
3. **Fallback** — wraps `str(event)` as `{"value": "..."}`

### Metadata added to each log entry

| Key | Value |
|-----|-------|
| `event_name` | `type(event).__name__` |
| `event_source` | The `event_source` passed at construction |
| `event_tag` | The normalized integer event tag |

### Structured logging

The logger is called with `extra={"event_data": event_dict}`, making the full event data available to log handlers that support structured output (e.g. `python-json-logger`).

## Combining Tracking and Reporting

Both can be attached to the same publisher simultaneously:

```python
tracker = TrackingEventSubscriber(event_source="debug")
reporter = ReportingEventSubscriber(event_source="production")

publisher.add_subscriber(tracker)
publisher.add_subscriber(reporter)
```
