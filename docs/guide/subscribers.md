# Subscribers

Subscribers receive events from publishers. EventsPype provides several subscriber types for different use cases.

## EventSubscriber

`EventSubscriber` is the abstract base class. Subclass it and implement `call`:

```python
from eventspype import EventSubscriber

class PrintSubscriber(EventSubscriber):
    def call(self, event, event_tag, caller):
        print(f"Event received: {event}")
```

The `call` method signature:

| Parameter | Type | Description |
|-----------|------|-------------|
| `event` | `Any` | The event object dispatched by the publisher |
| `event_tag` | `int` | The normalized integer event tag |
| `caller` | `Any` | The publisher that dispatched the event |

`EventSubscriber` is also callable — invoking an instance directly calls `call`:

```python
subscriber = PrintSubscriber()
subscriber(event_object, event_tag, caller)  # same as subscriber.call(...)
```

## OwnedEventSubscriber

`OwnedEventSubscriber` is a subscriber that holds a reference to an owner object. This is useful when a subscriber is created inline but needs to access an enclosing object:

```python
from eventspype import OwnedEventSubscriber

class MyService:
    def __init__(self):
        self._handler = OwnedEventSubscriber(owner=self)
        # Extend by subclassing OwnedEventSubscriber
```

## FunctionalEventSubscriber

`FunctionalEventSubscriber` wraps a plain callable as a subscriber. It supports two modes:

**With event info** (`with_event_info=True`, default): the callback receives `(event, event_tag, caller)`:

```python
from eventspype import FunctionalEventSubscriber

def my_handler(event, event_tag, caller):
    print(f"Tag {event_tag}: {event}")

subscriber = FunctionalEventSubscriber(my_handler, with_event_info=True)
publisher.add_subscriber(subscriber)
```

**Without event info** (`with_event_info=False`): the callback receives only `(event,)`:

```python
def simple_handler(event):
    print(event)

subscriber = FunctionalEventSubscriber(simple_handler, with_event_info=False)
publisher.add_subscriber(subscriber)
```

The preferred way to use functional subscribers is through `MultiPublisher.add_subscriber_with_callback()`, which manages the subscriber lifecycle automatically.

## MultiSubscriber

`MultiSubscriber` allows declarative subscription wiring. Define `EventSubscription` class attributes, then call `add_subscription` with a publisher instance at runtime.

```python
import logging
from eventspype import MultiSubscriber, EventSubscription

class OrderHandler(MultiSubscriber):
    on_order_placed = EventSubscription(
        publisher_class=OrderService,
        event_tag="order_placed",
        callback=lambda self, event, tag, caller: self.handle_placed(event),
    )

    def logger(self) -> logging.Logger:
        return logging.getLogger(__name__)

    def handle_placed(self, event) -> None:
        print(f"Handling order: {event.order_id}")

service = OrderService()
handler = OrderHandler()
handler.add_subscription(handler.on_order_placed, service)
```

!!! note
    `MultiSubscriber` requires you to implement the abstract `logger()` method.

### Managing subscriptions

```python
# Add a subscription
handler.add_subscription(handler.on_order_placed, service)

# Remove a subscription
handler.remove_subscription(handler.on_order_placed, service)
```

### Introspecting subscriptions

```python
# Get all defined subscriptions in the class hierarchy
definitions = OrderHandler.get_event_definitions()
# {'on_order_placed': <EventSubscription>}

# Access active subscriber objects
handler.subscribers  # dict[EventPublisher, dict[EventSubscription, list]]
```

### Subscribing to multiple tags

`EventSubscription` supports a list of event tags:

```python
on_order_events = EventSubscription(
    publisher_class=OrderService,
    event_tag=["order_placed", "order_cancelled"],
    callback=lambda self, event, tag, caller: self.handle_order(event, tag),
)
```

### Log decorator

`MultiSubscriber` provides a `log_event` decorator for adding automatic logging to handler methods:

```python
class OrderHandler(MultiSubscriber):
    @MultiSubscriber.log_event(log_level=logging.INFO, log_prefix="Order")
    def handle_placed(self, event) -> None:
        # Logged automatically before this method runs
        process(event)
```

## EventSubscription

`EventSubscription` connects a subscriber method to a specific publisher class and event tag:

```python
from eventspype import EventSubscription

subscription = EventSubscription(
    publisher_class=OrderService,       # must be EventPublisher or MultiPublisher subclass
    event_tag="order_placed",           # EventTag or list[EventTag]
    callback=my_callback,               # callable
    callback_with_subscriber=True,      # if True, callback receives self as first arg
    callback_with_event_info=True,      # if True, callback receives (event, tag, caller)
)
```

### PublicationSubscription

`PublicationSubscription` is a typed variant that wires directly to a specific `EventPublication` instance rather than a tag string. This avoids the tag lookup step and is useful when you have direct access to the publication object:

```python
from eventspype import PublicationSubscription

subscription = PublicationSubscription(
    publisher_class=OrderService,
    event_publication=OrderService.ORDER_PLACED,
    callback=my_callback,
)
```

## TrackingEventSubscriber

`TrackingEventSubscriber` collects received events for inspection or testing, and supports async waiting for specific event types.

```python
from eventspype import TrackingEventSubscriber

tracker = TrackingEventSubscriber(event_source="test", max_len=100)
publisher.add_subscriber(tracker)

publisher.publish(OrderPlacedEvent(1, 49.99))

# Inspect collected events
print(tracker.event_log)   # [OrderPlacedEvent(order_id=1, amount=49.99)]
tracker.clear()            # clear the log
```

### Async waiting

```python
import asyncio
from eventspype import TrackingEventSubscriber

async def main():
    tracker = TrackingEventSubscriber()
    publisher.add_subscriber(tracker)

    # Waits up to 10 seconds for an OrderPlacedEvent
    event = await tracker.wait_for(OrderPlacedEvent, timeout_seconds=10)
    print(f"Got: {event}")

asyncio.run(main())
```

`wait_for` raises `TimeoutError` if the event does not arrive within the timeout.

## ReportingEventSubscriber

`ReportingEventSubscriber` logs events using Python's `logging` module. It supports dataclasses, NamedTuples, and any object with `_asdict()`:

```python
from eventspype import ReportingEventSubscriber

reporter = ReportingEventSubscriber(event_source="order-service")
publisher.add_subscriber(reporter)

# Each event is logged at INFO level with metadata:
# Event received: {'order_id': 1, 'amount': 49.99,
#                  'event_name': 'OrderPlacedEvent',
#                  'event_source': 'order-service', 'event_tag': 12345}
```
