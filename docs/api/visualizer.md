# EventVisualizer

**Module:** `eventspype.viz.visualizer`

---

## EventVisualizer

```python
class EventVisualizer:
    def __init__(self) -> None
```

Generates graphviz directed graphs showing the architecture of an EventsPype system. Works with `MultiPublisher` and `MultiSubscriber` subclasses by reading their class-level `EventPublication` and `EventSubscription` attributes.

!!! note
    The `graphviz` Python package is a core dependency. The Graphviz system binaries must also be installed separately (`brew install graphviz` or `apt-get install graphviz`).

### Methods

#### `add_publisher`

```python
def add_publisher(self, publisher_class: type[MultiPublisher]) -> None
```

Register a `MultiPublisher` subclass for inclusion in the diagram. Reads `get_event_definitions()` to discover publications.

**Raises:** `ValueError` if `publisher_class` is not a `MultiPublisher` subclass.

---

#### `add_subscriber`

```python
def add_subscriber(self, subscriber_class: type[MultiSubscriber]) -> None
```

Register a `MultiSubscriber` subclass for inclusion in the diagram. Reads `get_event_definitions()` to discover subscriptions.

**Raises:** `ValueError` if `subscriber_class` is not a `MultiSubscriber` subclass.

---

#### `generate_graph`

```python
def generate_graph(
    self,
    graph_name: str = "EventSystem",
    graph_format: str = "png",
) -> graphviz.Digraph
```

Build and return a `graphviz.Digraph` object. Does not write any files.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `graph_name` | `str` | `"EventSystem"` | Name embedded in the graph |
| `graph_format` | `str` | `"png"` | Output format for subsequent renders |

**Returns:** `graphviz.Digraph`

---

#### `render`

```python
def render(
    self,
    output_path: str,
    graph_name: str = "EventSystem",
    graph_format: str = "png",
    view: bool = False,
) -> str
```

Render the diagram to a file and return the path.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `output_path` | `str` | — | File path without extension |
| `graph_name` | `str` | `"EventSystem"` | Name embedded in the graph |
| `graph_format` | `str` | `"png"` | Output format: `png`, `pdf`, `svg`, `dot`, etc. |
| `view` | `bool` | `False` | Open the rendered file with the system default viewer |

**Returns:** `str` — path to the rendered file.

---

#### `clear`

```python
def clear(self) -> None
```

Remove all registered publishers and subscribers.

### Diagram layout

The graph uses a left-to-right (`rankdir=LR`) layout with orthogonal splines:

- **Publisher nodes** (blue, `#E3F2FD` / `#1976D2`) — show class name and all `EventPublication` attributes with their original tags.
- **Subscriber nodes** (purple, `#F3E5F5` / `#7B1FA2`) — show class name and all `EventSubscription` attributes with tags and source publisher class name.
- **Edges** (green, `#4CAF50`) — drawn from each publisher to each subscriber where a subscription tag matches a publication tag.

### Example

```python
from eventspype import EventVisualizer, MultiPublisher, MultiSubscriber
from eventspype import EventPublication, EventSubscription
from dataclasses import dataclass
import logging

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
        callback=lambda self, e, t, c: None,
    )
    on_cancelled = EventSubscription(
        publisher_class=OrderService,
        event_tag="order_cancelled",
        callback=lambda self, e, t, c: None,
    )

    def logger(self) -> logging.Logger:
        return logging.getLogger(__name__)

viz = EventVisualizer()
viz.add_publisher(OrderService)
viz.add_subscriber(OrderHandler)

# Render to order_system.png
path = viz.render("order_system", graph_format="png")
print(f"Diagram: {path}")

# Or get the Digraph object for customization
graph = viz.generate_graph("OrderSystem", "svg")
graph.attr(bgcolor="white")
graph.render("custom_output")
```
