# Event Visualization

The eventspype framework now includes visualization capabilities to help you understand and document your event-driven architecture.

## Overview

The `EventVisualizer` class generates graphviz diagrams showing:
- **Publishers** with their event publications
- **Subscribers** with their event subscriptions
- **Connections** between publishers and subscribers based on matching event tags

## Installation

The visualization module requires the `graphviz` Python package (already included in dependencies) and the Graphviz system package:

```bash
# macOS
brew install graphviz

# Ubuntu/Debian
sudo apt-get install graphviz

# Windows
# Download from https://graphviz.org/download/
```

## Usage

### Basic Example

```python
from eventspype import EventVisualizer, MultiPublisher, MultiSubscriber

# Create visualizer
visualizer = EventVisualizer()

# Add your publisher and subscriber classes
visualizer.add_publisher(MyPublisher)
visualizer.add_subscriber(MySubscriber)

# Generate and save the diagram
visualizer.render("output_diagram", graph_format="png")
```

### Complete Example

See `examples/visualization_example.py` for a full working example demonstrating:
- Multiple publishers and subscribers
- Various event types
- Multi-event subscriptions
- Complete visualization workflow

### API Reference

#### EventVisualizer

**Methods:**

- `add_publisher(publisher_class: type[MultiPublisher]) -> None`
  - Add a publisher class to visualize

- `add_subscriber(subscriber_class: type[MultiSubscriber]) -> None`
  - Add a subscriber class to visualize

- `generate_graph(graph_name: str = "EventSystem", graph_format: str = "png") -> graphviz.Digraph`
  - Generate a graphviz Digraph object
  - Returns the graph for further customization

- `render(output_path: str, graph_name: str = "EventSystem", graph_format: str = "png", view: bool = False) -> str`
  - Render the graph to a file
  - Returns the path to the generated file
  - Set `view=True` to automatically open the diagram

- `clear() -> None`
  - Clear all publishers and subscribers from the visualizer

**Supported Formats:**
- png (default)
- pdf
- svg
- dot
- and more (see graphviz documentation)

## Visualization Features

### Static Analysis

The visualizer performs static analysis by:
1. Introspecting `MultiPublisher` classes using `get_event_definitions()`
2. Introspecting `MultiSubscriber` classes using `get_event_definitions()`
3. Matching publications to subscriptions by comparing event tags
4. Generating a directed graph with styled nodes and edges

### Visual Elements

- **Publisher Nodes**: Blue rounded boxes listing all event publications
- **Subscriber Nodes**: Purple rounded boxes listing all event subscriptions
- **Edges**: Green arrows labeled with the event tag connecting matching publishers to subscribers

### Event Tag Formatting

Event tags are displayed in a readable format:
- Enum tags: `EventTag.USER_CREATED`
- String tags: `"user_created"`
- Integer tags: `123`

## Example Output

The visualizer creates diagrams like:

```
┌─────────────────────────┐
│   UserPublisher         │
│   Publisher             │
│                         │
│ Publications:           │
│ • user_created: ...     │
│ • user_updated: ...     │
└─────────────────────────┘
            │
            │ USER_CREATED
            ▼
┌─────────────────────────┐
│ EmailNotificationService│
│   Subscriber            │
│                         │
│ Subscriptions:          │
│ • on_user_created: ...  │
└─────────────────────────┘
```

## Testing

The visualization module includes comprehensive tests covering:
- Basic functionality (adding publishers/subscribers)
- Introspection capabilities
- Event tag matching logic
- Graph generation
- Rendering to files
- Integration workflows

Run the tests:
```bash
poetry run pytest tests/viz/ -v
```

## Use Cases

1. **Documentation**: Generate architecture diagrams for documentation
2. **Onboarding**: Help new team members understand the event flow
3. **Debugging**: Visualize complex event relationships
4. **Design Review**: Review and validate event-driven architecture
5. **Refactoring**: Identify tightly coupled components
