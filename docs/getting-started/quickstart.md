# Quick Start

This guide walks through the basics of EventsPype: defining events, creating a publisher, subscribing to events, and running a complete example.

## Defining an Event Type

An event is any Python object. Use a dataclass for structured data:

```python
from dataclasses import dataclass

@dataclass
class UserCreatedEvent:
    user_id: int
    username: str
```

You can optionally subclass `Event` as a marker:

```python
from eventspype import Event

@dataclass
class UserCreatedEvent(Event):
    user_id: int
    username: str
```

## Creating a Publication and Publisher

An `EventPublication` pairs an event tag with the expected event class. An `EventPublisher` uses that publication to validate and dispatch events:

```python
from eventspype import EventPublication, EventPublisher

publication = EventPublication("user_created", UserCreatedEvent)
publisher = EventPublisher(publication)
```

Event tags can be a string, integer, or enum value. Strings are hashed deterministically for internal use.

## Creating a Subscriber

Subclass `EventSubscriber` and implement `call`:

```python
from eventspype import EventSubscriber

class UserHandler(EventSubscriber):
    def call(self, event, event_tag, caller):
        print(f"New user: {event.username} (ID: {event.user_id})")
```

## Connecting Publisher to Subscriber

```python
handler = UserHandler()
publisher.add_subscriber(handler)
```

The publisher holds a weak reference to the handler, so it will not prevent garbage collection if the handler goes out of scope.

## Publishing an Event

```python
publisher.publish(UserCreatedEvent(user_id=1, username="alice"))
# New user: alice (ID: 1)
```

The publisher validates that the event is an instance of the declared class. Passing the wrong type raises `ValueError`.

## Complete Example

```python
from dataclasses import dataclass
from eventspype import Event, EventPublication, EventPublisher, EventSubscriber

@dataclass
class OrderPlacedEvent(Event):
    order_id: int
    amount: float

publication = EventPublication("order_placed", OrderPlacedEvent)
publisher = EventPublisher(publication)

class OrderLogger(EventSubscriber):
    def call(self, event, event_tag, caller):
        print(f"[Order {event.order_id}] Amount: ${event.amount:.2f}")

logger = OrderLogger()
publisher.add_subscriber(logger)

publisher.publish(OrderPlacedEvent(order_id=100, amount=49.99))
publisher.publish(OrderPlacedEvent(order_id=101, amount=129.00))
```

## Using Functional Subscribers

Register a plain callable instead of subclassing:

```python
from eventspype import MultiPublisher, EventPublication

class OrderService(MultiPublisher):
    ORDER_PLACED = EventPublication("order_placed", OrderPlacedEvent)
    ORDER_CANCELLED = EventPublication("order_cancelled", OrderPlacedEvent)

service = OrderService()

# Simple callback (event only)
def on_order(event):
    print(f"Order received: {event.order_id}")

service.add_subscriber_with_callback(
    OrderService.ORDER_PLACED,
    on_order,
    with_event_info=False,
)

# Detailed callback (event, tag, caller)
def on_order_detailed(event, event_tag, caller):
    print(f"Tag={event_tag}: order {event.order_id} from {caller}")

service.add_subscriber_with_callback(
    OrderService.ORDER_CANCELLED,
    on_order_detailed,
    with_event_info=True,
)
```

## Multi-Publisher Pattern

Define all event publications as class attributes on a `MultiPublisher` subclass:

```python
from dataclasses import dataclass
from eventspype import MultiPublisher, EventPublication

@dataclass
class UserCreatedEvent:
    user_id: int
    username: str

@dataclass
class UserUpdatedEvent:
    user_id: int
    new_username: str

class UserService(MultiPublisher):
    USER_CREATED = EventPublication("user_created", UserCreatedEvent)
    USER_UPDATED = EventPublication("user_updated", UserUpdatedEvent)

    def create_user(self, user_id: int, username: str) -> None:
        event = UserCreatedEvent(user_id=user_id, username=username)
        self.publish(self.USER_CREATED, event)

    def update_user(self, user_id: int, new_username: str) -> None:
        event = UserUpdatedEvent(user_id=user_id, new_username=new_username)
        self.publish(self.USER_UPDATED, event)
```

## Multi-Subscriber Pattern

Define subscriptions as class attributes on a `MultiSubscriber` subclass, then wire them to publisher instances at runtime:

```python
import logging
from eventspype import MultiSubscriber, EventSubscription

class UserEventHandler(MultiSubscriber):
    on_user_created = EventSubscription(
        publisher_class=UserService,
        event_tag="user_created",
        callback=lambda self, event, tag, caller: self.handle_created(event),
    )

    def logger(self) -> logging.Logger:
        return logging.getLogger(__name__)

    def handle_created(self, event: UserCreatedEvent) -> None:
        print(f"Handling creation of {event.username}")

service = UserService()
handler = UserEventHandler()
handler.add_subscription(handler.on_user_created, service)

service.create_user(1, "alice")
# Handling creation of alice
```

## Async Event Waiting

Use `TrackingEventSubscriber` to wait for a specific event type in async code:

```python
import asyncio
from eventspype import TrackingEventSubscriber

async def wait_for_user():
    tracker = TrackingEventSubscriber()
    publisher.add_subscriber(tracker)

    event = await tracker.wait_for(UserCreatedEvent, timeout_seconds=10)
    print(f"Got event: {event}")

asyncio.run(wait_for_user())
```

## Next Steps

- [Events Guide](../guide/events.md) --- Event types, tags, and filtering
- [Publishers Guide](../guide/publishers.md) --- Publication lifecycle and multi-publisher patterns
- [Subscribers Guide](../guide/subscribers.md) --- All subscriber types explained
- [Message Brokers](../guide/broker.md) --- Swap dispatch backends
