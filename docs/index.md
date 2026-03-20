# EventsPype

[![CI](https://github.com/gianlucapagliara/eventspype/actions/workflows/ci.yml/badge.svg)](https://github.com/gianlucapagliara/eventspype/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/gianlucapagliara/eventspype/branch/main/graph/badge.svg)](https://codecov.io/gh/gianlucapagliara/eventspype)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/eventspype)](https://pypi.org/project/eventspype/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A lightweight, type-safe Python framework for building event-driven applications. EventsPype provides a clean publisher-subscriber pattern implementation with support for multiple event types, async waiting, message brokers, and architecture visualization.

## Features

- **Type-Safe Events** --- Runtime type checking ensures events match their declared publication class
- **Multi-Publisher/Subscriber** --- Handle multiple event types with `MultiPublisher` and `MultiSubscriber`
- **Async Support** --- Await specific event types with `TrackingEventSubscriber.wait_for()`
- **Message Brokers** --- Swap between in-process (`LocalBroker`) and Redis (`RedisBroker`) dispatch
- **Functional Subscribers** --- Register plain callbacks without subclassing
- **Tracking & Reporting** --- Built-in subscribers for testing and structured logging
- **Architecture Visualization** --- Generate graphviz diagrams of your event system
- **Memory Safe** --- Weak references prevent lapsed subscriber memory leaks
- **Well Tested** --- Comprehensive test suite with high coverage

## Quick Example

```python
from dataclasses import dataclass
from eventspype import EventPublisher, EventPublication, EventSubscriber

@dataclass
class OrderPlacedEvent:
    order_id: int
    amount: float

publication = EventPublication("order_placed", OrderPlacedEvent)
publisher = EventPublisher(publication)

class OrderHandler(EventSubscriber):
    def call(self, event, event_tag, caller):
        print(f"Order {event.order_id}: ${event.amount:.2f}")

handler = OrderHandler()
publisher.add_subscriber(handler)
publisher.publish(OrderPlacedEvent(order_id=42, amount=99.95))
# Order 42: $99.95
```

## Architecture Overview

EventsPype is organized around three core abstractions:

- **Publications** describe an event channel: its tag (identifier) and the expected event class.
- **Publishers** hold a set of subscribers for a publication and dispatch events to them using weak references.
- **Subscribers** implement the `call` method that runs when an event arrives.

```
EventPublication         ── declares tag + event class
EventPublisher           ── dispatches to subscribers (weak refs)
└── MultiPublisher       ── one publisher per EventPublication class attribute

EventSubscriber          ── abstract base: override call()
├── FunctionalEventSubscriber  ── wraps a plain callable
├── TrackingEventSubscriber    ── collects events, supports async wait_for()
└── ReportingEventSubscriber   ── logs events via logging module

MultiSubscriber          ── wires EventSubscription class attributes automatically

MessageBroker (abstract)
├── LocalBroker          ── in-process dispatch (default)
└── RedisBroker          ── cross-process via Redis Pub/Sub

EventVisualizer          ── generates graphviz architecture diagrams
```

## Next Steps

- [Installation](getting-started/installation.md) --- Set up EventsPype in your project
- [Quick Start](getting-started/quickstart.md) --- Build your first publisher and subscriber
- [User Guide](guide/events.md) --- Learn about events, publishers, subscribers, and brokers
- [API Reference](api/event.md) --- Full API documentation
