# MultiPublisher

**Module:** `eventspype.pub.multipublisher`

---

## MultiPublisher

```python
class MultiPublisher:
    def __init__(self, broker: MessageBroker | None = None) -> None
```

A publisher that manages multiple `EventPublication` channels. Define publications as class-level `EventPublication` attributes; `MultiPublisher` creates one `EventPublisher` per publication on demand.

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `broker` | `MessageBroker \| None` | Optional broker applied to all internal publishers |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `broker` | `MessageBroker \| None` | Current broker. Settable; propagates to all internal publishers and migrates subscribers. |

### Class methods

#### `get_event_definitions`

```python
@classmethod
def get_event_definitions(cls) -> dict[str, EventPublication]
```

Return all `EventPublication` attributes defined in the class and its parent classes (MRO order, child class attributes take precedence).

---

#### `is_publication_valid`

```python
@classmethod
def is_publication_valid(
    cls, publication: EventPublication, raise_error: bool = True
) -> bool
```

Check whether a publication belongs to this class.

**Raises:** `ValueError` if invalid and `raise_error=True` (default).

---

#### `get_event_definition_by_tag`

```python
@classmethod
def get_event_definition_by_tag(cls, event_tag: EventTag) -> EventPublication
```

Return the `EventPublication` whose tag matches `event_tag`.

**Raises:** `ValueError` if no matching publication is found.

### Instance methods

#### `add_subscriber`

```python
def add_subscriber(
    self, publication: EventPublication, subscriber: EventSubscriber
) -> None
```

Register a subscriber for a specific publication. Creates the internal `EventPublisher` for that publication if it does not exist yet.

**Raises:** `ValueError` if `publication` is not defined on this class.

---

#### `remove_subscriber`

```python
def remove_subscriber(
    self, publication: EventPublication, subscriber: EventSubscriber
) -> None
```

Unregister a subscriber. Removes the internal publisher if it has no remaining subscribers.

---

#### `add_subscriber_with_callback`

```python
def add_subscriber_with_callback(
    self, publication: EventPublication, callback: Any, with_event_info: bool = True
) -> None
```

Wrap `callback` in a `FunctionalEventSubscriber` and register it. The publisher keeps a strong reference to the subscriber to prevent garbage collection.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `publication` | `EventPublication` | Target publication |
| `callback` | `Callable` | Function to call on each event |
| `with_event_info` | `bool` | If `True` (default), callback receives `(event, event_tag, caller)`. If `False`, callback receives only `(event,)`. |

---

#### `remove_subscriber_with_callback`

```python
def remove_subscriber_with_callback(
    self, publication: EventPublication, callback: Any
) -> None
```

Remove a previously registered callback subscriber.

---

#### `publish`

```python
def publish(
    self, publication: EventPublication, event: Any, caller: Any | None = None
) -> None
```

Dispatch an event on a specific publication channel. Does nothing if no subscribers are registered for that publication.

**Raises:** `ValueError` if `publication` is not defined on this class, or if `event` is the wrong type.

### Example

```python
from dataclasses import dataclass
from eventspype import MultiPublisher, EventPublication, EventSubscriber

@dataclass
class UserCreatedEvent:
    user_id: int
    username: str

@dataclass
class UserDeletedEvent:
    user_id: int

class UserService(MultiPublisher):
    USER_CREATED = EventPublication("user_created", UserCreatedEvent)
    USER_DELETED = EventPublication("user_deleted", UserDeletedEvent)

    def create_user(self, user_id: int, username: str) -> None:
        self.publish(self.USER_CREATED, UserCreatedEvent(user_id, username))

    def delete_user(self, user_id: int) -> None:
        self.publish(self.USER_DELETED, UserDeletedEvent(user_id))

service = UserService()

class AuditLog(EventSubscriber):
    def call(self, event, event_tag, caller):
        print(f"Audit: {type(event).__name__} — {event}")

audit = AuditLog()
service.add_subscriber(UserService.USER_CREATED, audit)
service.add_subscriber(UserService.USER_DELETED, audit)

service.create_user(1, "alice")
service.delete_user(1)
```
