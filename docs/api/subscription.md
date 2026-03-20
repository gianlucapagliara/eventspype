# EventSubscription / PublicationSubscription

**Module:** `eventspype.sub.subscription`

---

## EventSubscription

```python
class EventSubscription:
    def __init__(
        self,
        publisher_class: type[EventPublisher] | type[MultiPublisher],
        event_tag: EventTag | list[EventTag],
        callback: EventSubscriptionCallback,
        callback_with_subscriber: bool = True,
        callback_with_event_info: bool = True,
    ) -> None
```

Declarative subscription descriptor. Used as a class attribute on `MultiSubscriber` subclasses to define the wiring between a subscriber method and a publisher's event channel.

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `publisher_class` | `type[EventPublisher] \| type[MultiPublisher]` | The publisher class this subscription targets |
| `event_tag` | `EventTag \| list[EventTag]` | One or more event tags to subscribe to |
| `callback` | `EventSubscriptionCallback` | The handler callable |
| `callback_with_subscriber` | `bool` | If `True` (default), the callback is looked up on the subscriber instance by name (`getattr(subscriber, callback.__name__)`) or bound via `partial`. |
| `callback_with_event_info` | `bool` | If `True` (default), callback receives `(event, event_tag, caller)`. If `False`, only `(event,)`. |

### Callback types

```python
# With subscriber and event info (default)
callback = lambda self, event, tag, caller: self.handle(event)

# With subscriber, without event info
EventSubscription(..., callback_with_event_info=False,
                  callback=lambda self, event: self.handle(event))

# Without subscriber (callback_with_subscriber=False)
EventSubscription(..., callback_with_subscriber=False,
                  callback=lambda event, tag, caller: handle(event))
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `publisher_class` | `type` | The declared publisher class |
| `event_tag` | `EventTag \| list[EventTag]` | The declared event tag(s) |
| `callback` | `Callable` | The handler callable |
| `callback_with_subscriber` | `bool` | Whether callback is bound to the subscriber |
| `event_tag_str` | `str` | String representation of the tag(s) for display |

### Methods

#### `subscribe`

```python
def subscribe(
    self,
    publisher: EventPublisher | MultiPublisher,
    subscriber: Any,
) -> list[FunctionalEventSubscriber]
```

Create and register `FunctionalEventSubscriber` instances on the publisher. Returns the list of created subscriber objects (one per tag).

---

#### `unsubscribe`

```python
def unsubscribe(
    self,
    publisher: EventPublisher | MultiPublisher,
    subscriber: FunctionalEventSubscriber,
) -> None
```

Remove a subscriber from the publisher.

### Example

```python
import logging
from eventspype import MultiSubscriber, EventSubscription, MultiPublisher, EventPublication
from dataclasses import dataclass

@dataclass
class PaymentEvent:
    payment_id: int
    amount: float

class PaymentService(MultiPublisher):
    PAYMENT_RECEIVED = EventPublication("payment_received", PaymentEvent)

class PaymentHandler(MultiSubscriber):
    # Single tag
    on_payment = EventSubscription(
        publisher_class=PaymentService,
        event_tag="payment_received",
        callback=lambda self, event, tag, caller: self.handle(event),
    )

    def logger(self) -> logging.Logger:
        return logging.getLogger(__name__)

    def handle(self, event: PaymentEvent) -> None:
        print(f"Payment {event.payment_id}: ${event.amount}")
```

---

## PublicationSubscription

```python
class PublicationSubscription(EventSubscription):
    def __init__(
        self,
        publisher_class: type[MultiPublisher],
        event_publication: EventPublication,
        callback: Callable[..., Any],
        callback_with_subscriber: bool = True,
        callback_with_event_info: bool = True,
    ) -> None
```

A typed variant of `EventSubscription` that wires directly to a specific `EventPublication` instance rather than performing a tag lookup. Use this when you have a direct reference to the publication object.

### Additional parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `publisher_class` | `type[MultiPublisher]` | Must be a `MultiPublisher` subclass |
| `event_publication` | `EventPublication` | The exact publication to subscribe to (bypasses tag lookup) |

### Example

```python
from eventspype import PublicationSubscription, MultiSubscriber
import logging

class PaymentHandler(MultiSubscriber):
    on_payment = PublicationSubscription(
        publisher_class=PaymentService,
        event_publication=PaymentService.PAYMENT_RECEIVED,
        callback=lambda self, event, tag, caller: self.handle(event),
    )

    def logger(self) -> logging.Logger:
        return logging.getLogger(__name__)

    def handle(self, event: PaymentEvent) -> None:
        print(f"Payment: {event}")
```
