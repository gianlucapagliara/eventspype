from dataclasses import dataclass
from enum import Enum

import pytest

from eventspype.event import Event
from eventspype.pub.multipublisher import MultiPublisher
from eventspype.pub.publication import EventPublication
from eventspype.sub.multisubscriber import MultiSubscriber
from eventspype.sub.subscription import EventSubscription
from eventspype.viz.visualizer import EventVisualizer


# Test fixtures - Event definitions
class TestEventTag(Enum):
    USER_CREATED = 1
    USER_UPDATED = 2
    USER_DELETED = 3
    ORDER_PLACED = 4


@dataclass
class UserCreatedEvent(Event):
    user_id: int
    username: str


@dataclass
class UserUpdatedEvent(Event):
    user_id: int
    username: str


@dataclass
class UserDeletedEvent(Event):
    user_id: int


@dataclass
class OrderPlacedEvent(Event):
    order_id: int
    user_id: int


# Test fixtures - Publisher
class TestUserPublisher(MultiPublisher):
    user_created = EventPublication(TestEventTag.USER_CREATED, UserCreatedEvent)
    user_updated = EventPublication(TestEventTag.USER_UPDATED, UserUpdatedEvent)
    user_deleted = EventPublication(TestEventTag.USER_DELETED, UserDeletedEvent)


class TestOrderPublisher(MultiPublisher):
    order_placed = EventPublication(TestEventTag.ORDER_PLACED, OrderPlacedEvent)


# Test fixtures - Subscriber
class TestUserSubscriber(MultiSubscriber):
    on_user_created = EventSubscription(
        TestUserPublisher,
        TestEventTag.USER_CREATED,
        lambda self, event: None,
    )
    on_user_updated = EventSubscription(
        TestUserPublisher,
        TestEventTag.USER_UPDATED,
        lambda self, event: None,
    )


class TestOrderSubscriber(MultiSubscriber):
    on_order_placed = EventSubscription(
        TestOrderPublisher,
        TestEventTag.ORDER_PLACED,
        lambda self, event: None,
    )


class TestMultiEventSubscriber(MultiSubscriber):
    on_user_events = EventSubscription(
        TestUserPublisher,
        [TestEventTag.USER_CREATED, TestEventTag.USER_DELETED],
        lambda self, event: None,
    )


class TestVisualizerBasics:
    """Test basic visualizer functionality."""

    def test_create_visualizer(self) -> None:
        """Test that a visualizer can be created."""
        visualizer = EventVisualizer()
        assert visualizer is not None

    def test_add_publisher(self) -> None:
        """Test adding a publisher to the visualizer."""
        visualizer = EventVisualizer()
        visualizer.add_publisher(TestUserPublisher)
        assert TestUserPublisher in visualizer._publishers

    def test_add_subscriber(self) -> None:
        """Test adding a subscriber to the visualizer."""
        visualizer = EventVisualizer()
        visualizer.add_subscriber(TestUserSubscriber)
        assert TestUserSubscriber in visualizer._subscribers

    def test_add_invalid_publisher_raises(self) -> None:
        """Test that adding an invalid publisher raises an error."""
        visualizer = EventVisualizer()

        class NotAPublisher:
            pass

        with pytest.raises(ValueError, match="must be a subclass of MultiPublisher"):
            visualizer.add_publisher(NotAPublisher)  # type: ignore

    def test_add_invalid_subscriber_raises(self) -> None:
        """Test that adding an invalid subscriber raises an error."""
        visualizer = EventVisualizer()

        class NotASubscriber:
            pass

        with pytest.raises(ValueError, match="must be a subclass of MultiSubscriber"):
            visualizer.add_subscriber(NotASubscriber)  # type: ignore

    def test_clear(self) -> None:
        """Test clearing the visualizer."""
        visualizer = EventVisualizer()
        visualizer.add_publisher(TestUserPublisher)
        visualizer.add_subscriber(TestUserSubscriber)

        visualizer.clear()

        assert len(visualizer._publishers) == 0
        assert len(visualizer._subscribers) == 0


class TestVisualizerIntrospection:
    """Test visualizer introspection capabilities."""

    def test_extract_publications(self) -> None:
        """Test extracting publications from a publisher."""
        visualizer = EventVisualizer()
        visualizer.add_publisher(TestUserPublisher)

        publications = visualizer._publishers[TestUserPublisher]
        assert "user_created" in publications
        assert "user_updated" in publications
        assert "user_deleted" in publications

    def test_extract_subscriptions(self) -> None:
        """Test extracting subscriptions from a subscriber."""
        visualizer = EventVisualizer()
        visualizer.add_subscriber(TestUserSubscriber)

        subscriptions = visualizer._subscribers[TestUserSubscriber]
        assert "on_user_created" in subscriptions
        assert "on_user_updated" in subscriptions

    def test_multiple_publishers(self) -> None:
        """Test adding multiple publishers."""
        visualizer = EventVisualizer()
        visualizer.add_publisher(TestUserPublisher)
        visualizer.add_publisher(TestOrderPublisher)

        assert len(visualizer._publishers) == 2
        assert TestUserPublisher in visualizer._publishers
        assert TestOrderPublisher in visualizer._publishers

    def test_multiple_subscribers(self) -> None:
        """Test adding multiple subscribers."""
        visualizer = EventVisualizer()
        visualizer.add_subscriber(TestUserSubscriber)
        visualizer.add_subscriber(TestOrderSubscriber)

        assert len(visualizer._subscribers) == 2
        assert TestUserSubscriber in visualizer._subscribers
        assert TestOrderSubscriber in visualizer._subscribers


class TestVisualizerMatching:
    """Test event tag matching logic."""

    def test_find_matches_simple(self) -> None:
        """Test finding matches between publications and subscriptions."""
        visualizer = EventVisualizer()
        visualizer.add_publisher(TestUserPublisher)
        visualizer.add_subscriber(TestUserSubscriber)

        publications = visualizer._publishers[TestUserPublisher]
        subscriptions = visualizer._subscribers[TestUserSubscriber]

        matches = visualizer._find_matches(
            TestUserPublisher, publications, subscriptions
        )

        # Should match USER_CREATED and USER_UPDATED
        assert len(matches) == 2
        match_tags = [match[2] for match in matches]
        assert "TestEventTag.USER_CREATED" in match_tags
        assert "TestEventTag.USER_UPDATED" in match_tags

    def test_find_matches_multi_event_subscription(self) -> None:
        """Test finding matches with multi-event subscriptions."""
        visualizer = EventVisualizer()
        visualizer.add_publisher(TestUserPublisher)
        visualizer.add_subscriber(TestMultiEventSubscriber)

        publications = visualizer._publishers[TestUserPublisher]
        subscriptions = visualizer._subscribers[TestMultiEventSubscriber]

        matches = visualizer._find_matches(
            TestUserPublisher, publications, subscriptions
        )

        # Should match USER_CREATED and USER_DELETED
        assert len(matches) == 2
        match_tags = [match[2] for match in matches]
        assert "TestEventTag.USER_CREATED" in match_tags
        assert "TestEventTag.USER_DELETED" in match_tags

    def test_no_matches(self) -> None:
        """Test when there are no matches between publisher and subscriber."""
        visualizer = EventVisualizer()
        visualizer.add_publisher(TestUserPublisher)
        visualizer.add_subscriber(TestOrderSubscriber)

        publications = visualizer._publishers[TestUserPublisher]
        subscriptions = visualizer._subscribers[TestOrderSubscriber]

        matches = visualizer._find_matches(
            TestUserPublisher, publications, subscriptions
        )

        assert len(matches) == 0

    def test_format_tag_enum(self) -> None:
        """Test formatting an enum tag."""
        visualizer = EventVisualizer()
        formatted = visualizer._format_tag(TestEventTag.USER_CREATED)
        assert formatted == "TestEventTag.USER_CREATED"

    def test_format_tag_string(self) -> None:
        """Test formatting a string tag."""
        visualizer = EventVisualizer()
        formatted = visualizer._format_tag("test_event")
        assert formatted == '"test_event"'

    def test_format_tag_integer(self) -> None:
        """Test formatting an integer tag."""
        visualizer = EventVisualizer()
        formatted = visualizer._format_tag(123)
        assert formatted == "123"


class TestVisualizerGraphGeneration:
    """Test graph generation functionality."""

    def test_generate_empty_graph(self) -> None:
        """Test generating a graph with no publishers or subscribers."""
        visualizer = EventVisualizer()
        graph = visualizer.generate_graph()
        assert graph is not None
        assert graph.name == "EventSystem"

    def test_generate_graph_with_publisher(self) -> None:
        """Test generating a graph with a publisher."""
        visualizer = EventVisualizer()
        visualizer.add_publisher(TestUserPublisher)
        graph = visualizer.generate_graph()

        assert graph is not None
        # Check that the graph contains the publisher node
        graph_source = graph.source
        assert "TestUserPublisher" in graph_source
        assert "Publisher" in graph_source

    def test_generate_graph_with_subscriber(self) -> None:
        """Test generating a graph with a subscriber."""
        visualizer = EventVisualizer()
        visualizer.add_subscriber(TestUserSubscriber)
        graph = visualizer.generate_graph()

        assert graph is not None
        # Check that the graph contains the subscriber node
        graph_source = graph.source
        assert "TestUserSubscriber" in graph_source
        assert "Subscriber" in graph_source

    def test_generate_graph_with_connections(self) -> None:
        """Test generating a graph with connected publisher and subscriber."""
        visualizer = EventVisualizer()
        visualizer.add_publisher(TestUserPublisher)
        visualizer.add_subscriber(TestUserSubscriber)
        graph = visualizer.generate_graph()

        assert graph is not None
        graph_source = graph.source
        # Check that both nodes and edges are present
        assert "TestUserPublisher" in graph_source
        assert "TestUserSubscriber" in graph_source
        assert (
            "USER_CREATED" in graph_source
            or "TestEventTag.USER_CREATED" in graph_source
        )

    def test_generate_graph_custom_name_and_format(self) -> None:
        """Test generating a graph with custom name and format."""
        visualizer = EventVisualizer()
        visualizer.add_publisher(TestUserPublisher)
        graph = visualizer.generate_graph(
            graph_name="CustomEventSystem", graph_format="svg"
        )

        assert graph is not None
        assert graph.name == "CustomEventSystem"
        assert graph.format == "svg"

    def test_generate_graph_multiple_publishers_subscribers(self) -> None:
        """Test generating a complex graph with multiple publishers and subscribers."""
        visualizer = EventVisualizer()
        visualizer.add_publisher(TestUserPublisher)
        visualizer.add_publisher(TestOrderPublisher)
        visualizer.add_subscriber(TestUserSubscriber)
        visualizer.add_subscriber(TestOrderSubscriber)

        graph = visualizer.generate_graph()

        assert graph is not None
        graph_source = graph.source
        assert "TestUserPublisher" in graph_source
        assert "TestOrderPublisher" in graph_source
        assert "TestUserSubscriber" in graph_source
        assert "TestOrderSubscriber" in graph_source


class TestVisualizerRender:
    """Test rendering functionality."""

    def test_render_creates_graph(self, tmp_path) -> None:
        """Test that render creates a graph file."""
        visualizer = EventVisualizer()
        visualizer.add_publisher(TestUserPublisher)
        visualizer.add_subscriber(TestUserSubscriber)

        output_path = str(tmp_path / "test_graph")
        result = visualizer.render(output_path, view=False)

        # The render method returns the path to the generated file
        assert result is not None
        assert isinstance(result, str)

    def test_render_with_custom_format(self, tmp_path) -> None:
        """Test rendering with a custom format."""
        visualizer = EventVisualizer()
        visualizer.add_publisher(TestUserPublisher)

        output_path = str(tmp_path / "test_graph")
        result = visualizer.render(output_path, graph_format="svg", view=False)

        assert result is not None
        assert result.endswith(".svg")


class TestVisualizerIntegration:
    """Integration tests for the visualizer."""

    def test_full_workflow(self, tmp_path) -> None:
        """Test the full workflow from adding classes to rendering."""
        visualizer = EventVisualizer()

        # Add publishers and subscribers
        visualizer.add_publisher(TestUserPublisher)
        visualizer.add_publisher(TestOrderPublisher)
        visualizer.add_subscriber(TestUserSubscriber)
        visualizer.add_subscriber(TestOrderSubscriber)
        visualizer.add_subscriber(TestMultiEventSubscriber)

        # Generate graph
        graph = visualizer.generate_graph()
        assert graph is not None

        # Render to file
        output_path = str(tmp_path / "full_test")
        result = visualizer.render(output_path, view=False)
        assert result is not None

        # Clear and verify
        visualizer.clear()
        assert len(visualizer._publishers) == 0
        assert len(visualizer._subscribers) == 0

    def test_reusable_visualizer(self, tmp_path) -> None:
        """Test that a visualizer can be reused for multiple graphs."""
        visualizer = EventVisualizer()

        # First graph
        visualizer.add_publisher(TestUserPublisher)
        visualizer.add_subscriber(TestUserSubscriber)
        graph1 = visualizer.generate_graph()
        assert graph1 is not None

        # Clear and create second graph
        visualizer.clear()
        visualizer.add_publisher(TestOrderPublisher)
        visualizer.add_subscriber(TestOrderSubscriber)
        graph2 = visualizer.generate_graph()
        assert graph2 is not None

        # Verify graphs are different
        assert "TestUserPublisher" in graph1.source
        assert "TestUserPublisher" not in graph2.source
        assert "TestOrderPublisher" not in graph1.source
        assert "TestOrderPublisher" in graph2.source
