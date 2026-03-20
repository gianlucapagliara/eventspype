# Publishers

Publishers are responsible for dispatching events to registered subscribers. EventsPype provides two publisher classes: `EventPublisher` for a single event type and `MultiPublisher` for multiple event types.

## EventPublication

Before creating a publisher you must define a publication. An `EventPublication` pairs an event tag with the expected event class:

```python
from dataclasses import dataclass
from eventspype import EventPublication

@dataclass
class OrderPlacedEvent:
    order_id: int
    amount: float

publication = EventPublication("order_placed", OrderPlacedEvent)
```

The `event_tag` can be an `Enum`, `int`, or `str`. The `event_class` is the type that will be enforced at publish time.

## EventPublisher

`EventPublisher` manages subscriptions and dispatch for a single `EventPublication`:

```python
from eventspype import EventPublisher

publisher = EventPublisher(publication)
```

### Adding and removing subscribers

```python
from eventspype import EventSubscriber

class MyHandler(EventSubscriber):
    def call(self, event, event_tag, caller):
        print(event)

handler = MyHandler()
publisher.add_subscriber(handler)

# Later:
publisher.remove_subscriber(handler)
```

### Publishing events

```python
publisher.publish(OrderPlacedEvent(order_id=1, amount=99.0))
```

The publisher validates that the event is an instance of the declared class. If not, it raises `ValueError`.

### Weak references and memory safety

`EventPublisher` stores subscribers as **weak references**. If a subscriber is garbage-collected (no other reference exists), it is automatically removed from the publisher. This prevents the "lapsed subscriber" memory leak.

```python
def create_transient_subscriber(publisher):
    handler = MyHandler()
    publisher.add_subscriber(handler)
    # handler goes out of scope here — publisher will clean it up automatically

create_transient_subscriber(publisher)
```

### Using a broker

Pass a `MessageBroker` to route events through an external system:

```python
from eventspype import LocalBroker

broker = LocalBroker()
publisher = EventPublisher(publication, broker=broker)
```

You can also change the broker after creation:

```python
publisher.broker = new_broker  # migrates existing subscribers automatically
```

## MultiPublisher

`MultiPublisher` manages one `EventPublisher` per publication. Define publications as class-level attributes:

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
        self.publish(self.USER_CREATED, UserCreatedEvent(user_id, username))

    def update_user(self, user_id: int, new_username: str) -> None:
        self.publish(self.USER_UPDATED, UserUpdatedEvent(user_id, new_username))
```

### Managing subscribers

```python
service = UserService()

# Add a typed subscriber
service.add_subscriber(UserService.USER_CREATED, handler)

# Add a callback subscriber
service.add_subscriber_with_callback(
    UserService.USER_CREATED,
    lambda event: print(f"Created: {event.username}"),
    with_event_info=False,
)

# Remove a subscriber
service.remove_subscriber(UserService.USER_CREATED, handler)

# Remove a callback subscriber
service.remove_subscriber_with_callback(UserService.USER_CREATED, my_callback)
```

### Introspecting publications

```python
# Get all defined publications
definitions = UserService.get_event_definitions()
# {'USER_CREATED': <EventPublication>, 'USER_UPDATED': <EventPublication>}

# Check if a publication belongs to this class
UserService.is_publication_valid(UserService.USER_CREATED)  # True

# Look up a publication by tag
pub = UserService.get_event_definition_by_tag("user_created")
```

### Inheritance

`MultiPublisher` traverses the MRO, so subclasses inherit publications from parent classes:

```python
class ExtendedUserService(UserService):
    USER_DELETED = EventPublication("user_deleted", UserDeletedEvent)

# ExtendedUserService has USER_CREATED, USER_UPDATED, and USER_DELETED
ExtendedUserService.get_event_definitions()
```

## Publication Lifecycle

1. Create an `EventPublication` with a tag and event class.
2. Attach it to an `EventPublisher` (directly or via `MultiPublisher`).
3. Add subscribers.
4. Call `publish()` — the publisher validates the event type, then dispatches to all live subscribers.
5. Dead subscriber references are cleaned up periodically (on `add_subscriber` with probability 0.005) and on every `publish` cycle.
