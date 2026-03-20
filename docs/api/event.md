# Event

**Module:** `eventspype.event`

---

## EventTag

```python
EventTag = Enum | int | str
```

Type alias for event tag values. Publishers and subscriptions accept any of these three types.

- **`Enum`** values use their `.value` (must be an `int`) as the internal tag.
- **`int`** values are used directly.
- **`str`** values are hashed deterministically using MD5 (case-insensitive) to an `int`.

---

## Event

```python
class Event
```

Optional marker base class for event types. Provides no behaviour; use it to signal intent in type annotations.

### Example

```python
from dataclasses import dataclass
from eventspype import Event

@dataclass
class OrderPlacedEvent(Event):
    order_id: int
    amount: float
```

Events do **not** have to subclass `Event`. Any Python object is accepted by `EventPublisher.publish()`, subject to the type check against the declared `EventPublication.event_class`.
