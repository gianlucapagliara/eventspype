# EventsPype

[![CI](https://github.com/gianlucapagliara/eventspype/actions/workflows/ci.yml/badge.svg)](https://github.com/gianlucapagliara/eventspype/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/gianlucapagliara/eventspype/branch/main/graph/badge.svg)](https://codecov.io/gh/gianlucapagliara/eventspype)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/eventspype)](https://pypi.org/project/eventspype/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://gianlucapagliara.github.io/eventspype/)

A lightweight, type-safe Python framework for building event-driven applications. EventsPype provides a clean publisher-subscriber pattern implementation with support for multiple event types, async waiting, message brokers, and architecture visualization.

## Features

- 🎯 **Type-Safe Events**: Runtime type checking ensures events match their declared publication class
- 🔄 **Multi-Publisher/Subscriber**: Handle multiple event types with `MultiPublisher` and `MultiSubscriber`
- 🚀 **Async Support**: Await specific event types with `TrackingEventSubscriber.wait_for()`
- 🔌 **Message Brokers**: Swap between in-process (`LocalBroker`) and Redis (`RedisBroker`) dispatch
- 🛠️ **Functional Subscribers**: Register plain callbacks without subclassing
- 📊 **Tracking & Reporting**: Built-in subscribers for testing and structured logging
- 🖼️ **Architecture Visualization**: Generate graphviz diagrams of your event system
- 🔒 **Memory Safe**: Weak references prevent lapsed subscriber memory leaks
- 🧪 **Well Tested**: Comprehensive test suite with high coverage

## Installation

```bash
# Using pip
pip install eventspype

# Using uv
uv add eventspype
```

## Quick Start

```python
from dataclasses import dataclass
from eventspype import EventPublisher, EventPublication, EventSubscriber

# Define an event type
@dataclass
class UserCreatedEvent:
    user_id: int
    username: str

# Create a publication and publisher
publication = EventPublication("user_created", UserCreatedEvent)
publisher = EventPublisher(publication)

# Create a subscriber
class UserHandler(EventSubscriber):
    def call(self, event, event_tag, caller):
        print(f"User created: {event.username} (ID: {event.user_id})")

# Subscribe and publish
handler = UserHandler()
publisher.add_subscriber(handler)
publisher.publish(UserCreatedEvent(user_id=1, username="alice"))
```

## Core Components

- **Events**: Any Python object; `Event` is an optional base class. `EventTag` accepts enums, ints, or strings.
  - `Event`: Optional marker base class for event types
  - `EventTag`: Type alias for `Enum | int | str`

- **Publishers**: Dispatch events to registered subscribers
  - `EventPublisher`: Single-publication publisher with weak-reference subscriber management
  - `MultiPublisher`: Multi-publication publisher; define `EventPublication` attributes as class variables

- **Subscribers**: Receive and handle events
  - `EventSubscriber`: Abstract base class; override `call(event, event_tag, caller)`
  - `OwnedEventSubscriber`: Subscriber that holds a reference to an owner object
  - `FunctionalEventSubscriber`: Wraps a plain callable as a subscriber
  - `MultiSubscriber`: Define `EventSubscription` class attributes for declarative wiring

- **Subscriptions**: Declarative wiring between publishers and subscribers
  - `EventSubscription`: Connects a `MultiSubscriber` method to a publisher's event tag
  - `PublicationSubscription`: Typed variant that wires directly to an `EventPublication`

- **Brokers**: Pluggable event transport layer
  - `MessageBroker`: Abstract base class
  - `LocalBroker`: In-process dispatch (default behavior)
  - `RedisBroker`: Cross-process dispatch via Redis Pub/Sub

- **Utilities**
  - `TrackingEventSubscriber`: Collects events and supports `await wait_for(EventType)`
  - `ReportingEventSubscriber`: Logs events via Python's `logging` module
  - `EventVisualizer`: Generates graphviz architecture diagrams

## Documentation

Full documentation is available at [gianlucapagliara.github.io/eventspype](https://gianlucapagliara.github.io/eventspype/).

## Development

EventsPype uses [uv](https://docs.astral.sh/uv/) for dependency management and packaging:

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Run type checks
uv run mypy eventspype

# Run linting
uv run ruff check .

# Run pre-commit hooks
uv run pre-commit run --all-files
```
