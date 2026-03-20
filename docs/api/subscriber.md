# EventSubscriber

**Module:** `eventspype.sub.subscriber`

---

## EventSubscriber

```python
class EventSubscriber
```

Abstract base class for all event subscribers. Subclass it and implement `call`.

### Methods

#### `call` (abstract)

```python
@abstractmethod
def call(
    self,
    arg: Any,
    current_event_tag: int,
    current_event_caller: Any,
) -> None
```

Handle an incoming event. Called by the publisher for each dispatched event.

| Parameter | Type | Description |
|-----------|------|-------------|
| `arg` | `Any` | The event object |
| `current_event_tag` | `int` | Normalized integer event tag |
| `current_event_caller` | `Any` | The publisher that dispatched the event |

---

#### `__call__`

```python
def __call__(
    self, arg: Any, current_event_tag: int, current_event_caller: Any
) -> None
```

Makes the subscriber callable. Delegates to `call`. Publishers invoke subscribers via this method.

### Example

```python
from eventspype import EventSubscriber

class PrintSubscriber(EventSubscriber):
    def call(self, event, event_tag, caller):
        print(f"[tag={event_tag}] {event}")
```

---

## OwnedEventSubscriber

**Module:** `eventspype.sub.subscriber`

```python
class OwnedEventSubscriber(EventSubscriber):
    def __init__(self, owner: Any) -> None
```

A subscriber that holds a reference to an owning object. Useful for inline subscriber creation where the subscriber needs access to an enclosing context.

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `owner` | `Any` | The object that owns this subscriber |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `owner` | `Any` | The owner object passed at construction |

### Example

```python
from eventspype import OwnedEventSubscriber, EventPublisher

class MyService:
    def __init__(self, publisher: EventPublisher) -> None:
        self._subscriber = _ServiceSubscriber(owner=self)
        publisher.add_subscriber(self._subscriber)

class _ServiceSubscriber(OwnedEventSubscriber):
    def call(self, event, event_tag, caller):
        self.owner.handle_event(event)
```
