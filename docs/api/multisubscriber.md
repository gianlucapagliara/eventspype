# MultiSubscriber

**Module:** `eventspype.sub.multisubscriber`

---

## MultiSubscriber

```python
class MultiSubscriber:
    def __init__(self) -> None
```

Base class for declarative subscription wiring. Define `EventSubscription` class attributes; at runtime call `add_subscription` to connect them to publisher instances.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `subscribers` | `dict[EventPublisher, dict[EventSubscription, Any]]` | Internal map of active subscriber objects keyed by publisher and subscription |

### Abstract methods

#### `logger` (abstract)

```python
@abstractmethod
def logger(self) -> logging.Logger
```

Return the logger for this subscriber. Required by all `MultiSubscriber` subclasses.

### Class methods

#### `get_event_definitions`

```python
@classmethod
def get_event_definitions(cls) -> dict[str, EventSubscription]
```

Return all `EventSubscription` attributes defined in the class and its parent classes (MRO order, child class attributes take precedence).

### Instance methods

#### `add_subscription`

```python
def add_subscription(
    self, subscription: EventSubscription, publisher: EventPublisher
) -> None
```

Activate a subscription by connecting it to a specific publisher instance.

**Raises:** `ValueError` if `subscription` is not defined on this class.

Does nothing if the subscription is already active for that publisher.

---

#### `remove_subscription`

```python
def remove_subscription(
    self, subscription: EventSubscription, publisher: EventPublisher
) -> None
```

Deactivate a subscription for a specific publisher.

**Raises:** `ValueError` if `subscription` is not defined on this class.

### Static methods

#### `log_event`

```python
@staticmethod
def log_event(
    log_level: int = logging.INFO, log_prefix: str = "Event"
) -> Callable
```

Decorator that logs the event before calling the decorated handler method. Uses `self.logger()`.

```python
class MyHandler(MultiSubscriber):
    @MultiSubscriber.log_event(log_level=logging.DEBUG, log_prefix="Order")
    def handle_placed(self, event) -> None:
        process(event)
```

### Example

```python
import logging
from eventspype import MultiSubscriber, EventSubscription, MultiPublisher, EventPublication
from dataclasses import dataclass

@dataclass
class ShipmentEvent:
    shipment_id: int

class ShipmentService(MultiPublisher):
    SHIPPED = EventPublication("shipped", ShipmentEvent)

class ShipmentHandler(MultiSubscriber):
    on_shipped = EventSubscription(
        publisher_class=ShipmentService,
        event_tag="shipped",
        callback=lambda self, event, tag, caller: self.handle(event),
    )

    def logger(self) -> logging.Logger:
        return logging.getLogger(__name__)

    def handle(self, event: ShipmentEvent) -> None:
        print(f"Shipment {event.shipment_id} sent")

service = ShipmentService()
handler = ShipmentHandler()
handler.add_subscription(handler.on_shipped, service)

service.publish(ShipmentService.SHIPPED, ShipmentEvent(shipment_id=99))
# Shipment 99 sent
```
