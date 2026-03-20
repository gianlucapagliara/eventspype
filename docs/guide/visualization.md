# Architecture Visualization

`EventVisualizer` generates graphviz diagrams that show the publishers, subscribers, and event connections in your system.

## Requirements

The `graphviz` Python package is a core dependency of EventsPype. You also need the Graphviz system binaries:

```bash
# macOS
brew install graphviz

# Ubuntu / Debian
sudo apt-get install graphviz
```

## Basic Usage

```python
from eventspype import EventVisualizer

visualizer = EventVisualizer()
visualizer.add_publisher(OrderService)
visualizer.add_subscriber(OrderHandler)

# Render to a PNG file (creates "architecture.png")
visualizer.render("architecture", graph_format="png")
```

## Defining Classes for Visualization

`EventVisualizer` works with `MultiPublisher` and `MultiSubscriber` subclasses. It reads the class-level `EventPublication` and `EventSubscription` attributes to build the diagram automatically.

```python
from dataclasses import dataclass
from eventspype import MultiPublisher, MultiSubscriber, EventPublication, EventSubscription

@dataclass
class OrderPlacedEvent:
    order_id: int

@dataclass
class OrderCancelledEvent:
    order_id: int

class OrderService(MultiPublisher):
    ORDER_PLACED = EventPublication("order_placed", OrderPlacedEvent)
    ORDER_CANCELLED = EventPublication("order_cancelled", OrderCancelledEvent)

class OrderHandler(MultiSubscriber):
    on_placed = EventSubscription(
        publisher_class=OrderService,
        event_tag="order_placed",
        callback=lambda self, event, tag, caller: None,
    )
    on_cancelled = EventSubscription(
        publisher_class=OrderService,
        event_tag="order_cancelled",
        callback=lambda self, event, tag, caller: None,
    )
```

## Rendering

### `render(output_path, graph_name, graph_format, view)`

Renders the diagram to a file and returns the output path:

```python
path = visualizer.render(
    output_path="docs/architecture",   # path without extension
    graph_name="OrderSystem",          # name shown in the diagram
    graph_format="png",                # png, pdf, svg, etc.
    view=False,                        # open with system viewer after rendering
)
print(f"Diagram saved to: {path}")
```

### `generate_graph(graph_name, graph_format)`

Returns a `graphviz.Digraph` object for further customization:

```python
graph = visualizer.generate_graph(graph_name="MySystem", graph_format="svg")
graph.attr(bgcolor="white")
graph.render("custom_output")
```

## Diagram Layout

The generated diagram uses a left-to-right layout:

- **Publisher nodes** (blue boxes) show the class name and all defined `EventPublication` attributes with their tags.
- **Subscriber nodes** (purple boxes) show the class name and all defined `EventSubscription` attributes with their tags and the source publisher class.
- **Edges** (green arrows) connect publishers to subscribers where the event tags match. The edge label shows the event tag.

## Supported Output Formats

Any format supported by Graphviz works: `png`, `pdf`, `svg`, `dot`, `jpg`, and more.

```python
visualizer.render("output", graph_format="svg")
visualizer.render("output", graph_format="pdf")
```

## Managing the Visualizer

```python
# Add multiple publishers and subscribers
visualizer.add_publisher(OrderService)
visualizer.add_publisher(UserService)
visualizer.add_subscriber(OrderHandler)
visualizer.add_subscriber(AuditHandler)

# Clear everything and start over
visualizer.clear()
```

## Complete Example

```python
from eventspype import EventVisualizer, MultiPublisher, MultiSubscriber
from eventspype import EventPublication, EventSubscription
from dataclasses import dataclass
import logging

@dataclass
class OrderPlacedEvent:
    order_id: int
    amount: float

@dataclass
class UserCreatedEvent:
    user_id: int
    username: str

class OrderService(MultiPublisher):
    ORDER_PLACED = EventPublication("order_placed", OrderPlacedEvent)

class UserService(MultiPublisher):
    USER_CREATED = EventPublication("user_created", UserCreatedEvent)

class AuditHandler(MultiSubscriber):
    on_order = EventSubscription(
        publisher_class=OrderService,
        event_tag="order_placed",
        callback=lambda self, e, t, c: None,
    )
    on_user = EventSubscription(
        publisher_class=UserService,
        event_tag="user_created",
        callback=lambda self, e, t, c: None,
    )

    def logger(self) -> logging.Logger:
        return logging.getLogger(__name__)

# Visualize
viz = EventVisualizer()
viz.add_publisher(OrderService)
viz.add_publisher(UserService)
viz.add_subscriber(AuditHandler)
viz.render("system_architecture", graph_format="png")
```
