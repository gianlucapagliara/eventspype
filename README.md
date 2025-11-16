# Events Pypeline

[![CI](https://github.com/gianlucapagliara/eventspype/actions/workflows/ci.yml/badge.svg)](https://github.com/gianlucapagliara/eventspype/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/gianlucapagliara/eventspype/branch/main/graph/badge.svg)](https://codecov.io/gh/gianlucapagliara/eventspype)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)

A lightweight and type-safe Python framework for building event-driven applications. eventspype provides a clean publisher-subscriber pattern implementation, making it easy to create decoupled and maintainable event-driven systems.

## Features

- 🎯 Type-safe publisher-subscriber pattern implementation
- 🔄 Support for multiple publishers and subscribers
- 🚀 Asynchronous event handling capabilities
- 🛠️ Easy to use and integrate
- 📦 Zero dependencies
- 🔒 Thread-safe event distribution

## Installation

```bash
# Using pip
pip install eventspype

# Using poetry
poetry add eventspype
```

## Quick Start

### Basic Publisher-Subscriber Pattern

```python
from dataclasses import dataclass
from enum import Enum
from eventspype import EventPublisher, EventPublication, EventSubscriber

# Define your event types
class MyEvents(Enum):
    USER_CREATED = 1
    USER_UPDATED = 2

@dataclass
class UserCreatedEvent:
    user_id: int
    username: str

# Create a publication for your event
user_created_pub = EventPublication(MyEvents.USER_CREATED, UserCreatedEvent)

# Create a publisher
publisher = EventPublisher(user_created_pub)

# Create a subscriber
class UserSubscriber(EventSubscriber):
    def call(self, event, event_tag, caller):
        print(f"User created: {event.username} (ID: {event.user_id})")

# Subscribe to events
subscriber = UserSubscriber()
publisher.add_subscriber(subscriber)

# Publish an event
event = UserCreatedEvent(user_id=123, username="john_doe")
publisher.publish(event)
```

### Using MultiPublisher for Multiple Event Types

```python
from eventspype import MultiPublisher, EventPublication

class NotificationService(MultiPublisher):
    # Define multiple event publications as class attributes
    USER_CREATED = EventPublication("user_created", UserCreatedEvent)
    USER_UPDATED = EventPublication("user_updated", UserUpdatedEvent)

    def create_user(self, user_id: int, username: str):
        # Your business logic here
        event = UserCreatedEvent(user_id=user_id, username=username)
        self.publish(self.USER_CREATED, event)

# Use the service
service = NotificationService()
service.add_subscriber(NotificationService.USER_CREATED, subscriber)
service.create_user(123, "john_doe")
```

### Using MultiSubscriber for Complex Subscriptions

```python
import logging
from eventspype import MultiSubscriber, EventSubscription

class UserEventHandler(MultiSubscriber):
    # Define subscriptions as class attributes
    on_user_created = EventSubscription(
        publisher_class=NotificationService,
        event_tag="user_created",
        callback=lambda self, event, tag, caller: self.handle_user_created(event),
    )

    def __init__(self):
        super().__init__()
        self._logger = logging.getLogger(__name__)

    def logger(self) -> logging.Logger:
        return self._logger

    def handle_user_created(self, event: UserCreatedEvent):
        print(f"Handling user creation: {event.username}")

# Set up the handler
handler = UserEventHandler()
service = NotificationService()
handler.add_subscription(handler.on_user_created, service)
```

### Functional Subscribers with Callbacks

```python
from eventspype import MultiPublisher, EventPublication

# Simple callback without event info
def simple_handler(event):
    print(f"Event received: {event}")

# Complete callback with event info
def detailed_handler(event, event_tag, caller):
    print(f"Event {event_tag} from {caller}: {event}")

service = NotificationService()

# Add callback subscriber (simple)
service.add_subscriber_with_callback(
    NotificationService.USER_CREATED,
    simple_handler,
    with_event_info=False
)

# Add callback subscriber (with event info)
service.add_subscriber_with_callback(
    NotificationService.USER_UPDATED,
    detailed_handler,
    with_event_info=True
)
```

### Event Tracking and Reporting

```python
from eventspype import TrackingEventSubscriber, ReportingEventSubscriber

# Track events for testing or debugging
tracker = TrackingEventSubscriber(event_source="test")
publisher.add_subscriber(tracker)

# Publish some events
publisher.publish(UserCreatedEvent(1, "user1"))
publisher.publish(UserCreatedEvent(2, "user2"))

# Access collected events
print(f"Collected {len(tracker.event_log)} events")
for event in tracker.event_log:
    print(f"  - {event}")

# Report events to logging system
reporter = ReportingEventSubscriber(event_source="production")
publisher.add_subscriber(reporter)
```

### Async Event Waiting

```python
import asyncio
from eventspype import TrackingEventSubscriber

async def wait_for_user_creation():
    tracker = TrackingEventSubscriber()
    publisher.add_subscriber(tracker)

    # Wait for a specific event type
    try:
        event = await tracker.wait_for(UserCreatedEvent, timeout_seconds=10)
        print(f"Received event: {event}")
    except asyncio.TimeoutError:
        print("Event did not occur within timeout")

# Run the async function
asyncio.run(wait_for_user_creation())
```

### Architecture Visualization

Generate graphviz diagrams of your event system architecture:

```python
from eventspype import EventVisualizer

# Create visualizer and add your classes
visualizer = EventVisualizer()
visualizer.add_publisher(NotificationService)
visualizer.add_subscriber(UserEventHandler)

# Generate diagram (requires: brew install graphviz)
visualizer.render("architecture", graph_format="png")
```

The visualizer creates diagrams showing publishers (blue boxes), subscribers (purple boxes), and their connections (green arrows), making it easy to understand and document your event-driven architecture. See `examples/visualization_example.py` for more details.

## Advanced Features

### Weak References

EventPublisher uses weak references to prevent memory leaks from "lapsed subscribers" (subscribers that are no longer referenced but haven't been explicitly unsubscribed). The publisher automatically cleans up dead subscriber references.

### Type Safety

The framework enforces type checking at runtime - publishers will validate that events match the declared event class in the publication, raising a `ValueError` if types don't match.

### Event Tags

Event tags can be:
- Enum values
- Integers
- Strings (automatically hashed to integers)

This provides flexibility in how you identify and organize your events.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
