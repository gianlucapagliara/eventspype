import pathlib
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
class VizEventTag(Enum):
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
class VizUserPublisher(MultiPublisher):
    user_created = EventPublication(VizEventTag.USER_CREATED, UserCreatedEvent)
    user_updated = EventPublication(VizEventTag.USER_UPDATED, UserUpdatedEvent)
    user_deleted = EventPublication(VizEventTag.USER_DELETED, UserDeletedEvent)


class VizOrderPublisher(MultiPublisher):
    order_placed = EventPublication(VizEventTag.ORDER_PLACED, OrderPlacedEvent)


# Test fixtures - Subscriber
class VizUserSubscriber(MultiSubscriber):
    on_user_created = EventSubscription(
        VizUserPublisher,
        VizEventTag.USER_CREATED,
        lambda self, event: None,
    )
    on_user_updated = EventSubscription(
        VizUserPublisher,
        VizEventTag.USER_UPDATED,
        lambda self, event: None,
    )


class VizOrderSubscriber(MultiSubscriber):
    on_order_placed = EventSubscription(
        VizOrderPublisher,
        VizEventTag.ORDER_PLACED,
        lambda self, event: None,
    )


class VizMultiEventSubscriber(MultiSubscriber):
    on_user_events = EventSubscription(
        VizUserPublisher,
        [VizEventTag.USER_CREATED, VizEventTag.USER_DELETED],
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
        visualizer.add_publisher(VizUserPublisher)
        assert VizUserPublisher in visualizer._publishers

    def test_add_subscriber(self) -> None:
        """Test adding a subscriber to the visualizer."""
        visualizer = EventVisualizer()
        visualizer.add_subscriber(VizUserSubscriber)
        assert VizUserSubscriber in visualizer._subscribers

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
        visualizer.add_publisher(VizUserPublisher)
        visualizer.add_subscriber(VizUserSubscriber)

        visualizer.clear()

        assert len(visualizer._publishers) == 0
        assert len(visualizer._subscribers) == 0


class TestVisualizerIntrospection:
    """Test visualizer introspection capabilities."""

    def test_extract_publications(self) -> None:
        """Test extracting publications from a publisher."""
        visualizer = EventVisualizer()
        visualizer.add_publisher(VizUserPublisher)

        publications = visualizer._publishers[VizUserPublisher]
        assert "user_created" in publications
        assert "user_updated" in publications
        assert "user_deleted" in publications

    def test_extract_subscriptions(self) -> None:
        """Test extracting subscriptions from a subscriber."""
        visualizer = EventVisualizer()
        visualizer.add_subscriber(VizUserSubscriber)

        subscriptions = visualizer._subscribers[VizUserSubscriber]
        assert "on_user_created" in subscriptions
        assert "on_user_updated" in subscriptions

    def test_multiple_publishers(self) -> None:
        """Test adding multiple publishers."""
        visualizer = EventVisualizer()
        visualizer.add_publisher(VizUserPublisher)
        visualizer.add_publisher(VizOrderPublisher)

        assert len(visualizer._publishers) == 2
        assert VizUserPublisher in visualizer._publishers
        assert VizOrderPublisher in visualizer._publishers

    def test_multiple_subscribers(self) -> None:
        """Test adding multiple subscribers."""
        visualizer = EventVisualizer()
        visualizer.add_subscriber(VizUserSubscriber)
        visualizer.add_subscriber(VizOrderSubscriber)

        assert len(visualizer._subscribers) == 2
        assert VizUserSubscriber in visualizer._subscribers
        assert VizOrderSubscriber in visualizer._subscribers


class TestVisualizerMatching:
    """Test event tag matching logic."""

    def test_find_matches_simple(self) -> None:
        """Test finding matches between publications and subscriptions."""
        visualizer = EventVisualizer()
        visualizer.add_publisher(VizUserPublisher)
        visualizer.add_subscriber(VizUserSubscriber)

        publications = visualizer._publishers[VizUserPublisher]
        subscriptions = visualizer._subscribers[VizUserSubscriber]

        matches = visualizer._find_matches(
            VizUserPublisher, publications, subscriptions
        )

        # Should match USER_CREATED and USER_UPDATED
        assert len(matches) == 2
        match_tags = [match[2] for match in matches]
        assert "VizEventTag.USER_CREATED" in match_tags
        assert "VizEventTag.USER_UPDATED" in match_tags

    def test_find_matches_multi_event_subscription(self) -> None:
        """Test finding matches with multi-event subscriptions."""
        visualizer = EventVisualizer()
        visualizer.add_publisher(VizUserPublisher)
        visualizer.add_subscriber(VizMultiEventSubscriber)

        publications = visualizer._publishers[VizUserPublisher]
        subscriptions = visualizer._subscribers[VizMultiEventSubscriber]

        matches = visualizer._find_matches(
            VizUserPublisher, publications, subscriptions
        )

        # Should match USER_CREATED and USER_DELETED
        assert len(matches) == 2
        match_tags = [match[2] for match in matches]
        assert "VizEventTag.USER_CREATED" in match_tags
        assert "VizEventTag.USER_DELETED" in match_tags

    def test_no_matches(self) -> None:
        """Test when there are no matches between publisher and subscriber."""
        visualizer = EventVisualizer()
        visualizer.add_publisher(VizUserPublisher)
        visualizer.add_subscriber(VizOrderSubscriber)

        publications = visualizer._publishers[VizUserPublisher]
        subscriptions = visualizer._subscribers[VizOrderSubscriber]

        matches = visualizer._find_matches(
            VizUserPublisher, publications, subscriptions
        )

        assert len(matches) == 0

    def test_format_tag_enum(self) -> None:
        """Test formatting an enum tag."""
        visualizer = EventVisualizer()
        formatted = visualizer._format_tag(VizEventTag.USER_CREATED)
        assert formatted == "VizEventTag.USER_CREATED"

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
        visualizer.add_publisher(VizUserPublisher)
        graph = visualizer.generate_graph()

        assert graph is not None
        # Check that the graph contains the publisher node
        graph_source = graph.source
        assert "VizUserPublisher" in graph_source
        assert "Publisher" in graph_source

    def test_generate_graph_with_subscriber(self) -> None:
        """Test generating a graph with a subscriber."""
        visualizer = EventVisualizer()
        visualizer.add_subscriber(VizUserSubscriber)
        graph = visualizer.generate_graph()

        assert graph is not None
        # Check that the graph contains the subscriber node
        graph_source = graph.source
        assert "VizUserSubscriber" in graph_source
        assert "Subscriber" in graph_source

    def test_generate_graph_with_connections(self) -> None:
        """Test generating a graph with connected publisher and subscriber."""
        visualizer = EventVisualizer()
        visualizer.add_publisher(VizUserPublisher)
        visualizer.add_subscriber(VizUserSubscriber)
        graph = visualizer.generate_graph()

        assert graph is not None
        graph_source = graph.source
        # Check that both nodes and edges are present
        assert "VizUserPublisher" in graph_source
        assert "VizUserSubscriber" in graph_source
        assert (
            "USER_CREATED" in graph_source or "VizEventTag.USER_CREATED" in graph_source
        )

    def test_generate_graph_custom_name_and_format(self) -> None:
        """Test generating a graph with custom name and format."""
        visualizer = EventVisualizer()
        visualizer.add_publisher(VizUserPublisher)
        graph = visualizer.generate_graph(
            graph_name="CustomEventSystem", graph_format="svg"
        )

        assert graph is not None
        assert graph.name == "CustomEventSystem"
        assert graph.format == "svg"

    def test_generate_graph_multiple_publishers_subscribers(self) -> None:
        """Test generating a complex graph with multiple publishers and subscribers."""
        visualizer = EventVisualizer()
        visualizer.add_publisher(VizUserPublisher)
        visualizer.add_publisher(VizOrderPublisher)
        visualizer.add_subscriber(VizUserSubscriber)
        visualizer.add_subscriber(VizOrderSubscriber)

        graph = visualizer.generate_graph()

        assert graph is not None
        graph_source = graph.source
        assert "VizUserPublisher" in graph_source
        assert "VizOrderPublisher" in graph_source
        assert "VizUserSubscriber" in graph_source
        assert "VizOrderSubscriber" in graph_source


class TestVisualizerRender:
    """Test rendering functionality."""

    def test_render_creates_graph(self, tmp_path: pathlib.Path) -> None:
        """Test that render creates a graph file."""
        visualizer = EventVisualizer()
        visualizer.add_publisher(VizUserPublisher)
        visualizer.add_subscriber(VizUserSubscriber)

        output_path = str(tmp_path / "test_graph")
        result = visualizer.render(output_path, view=False)

        # The render method returns the path to the generated file
        assert result is not None
        assert isinstance(result, str)

    def test_render_with_custom_format(self, tmp_path: pathlib.Path) -> None:
        """Test rendering with a custom format."""
        visualizer = EventVisualizer()
        visualizer.add_publisher(VizUserPublisher)

        output_path = str(tmp_path / "test_graph")
        result = visualizer.render(output_path, graph_format="svg", view=False)

        assert result is not None
        assert result.endswith(".svg")


class TestVisualizerIntegration:
    """Integration tests for the visualizer."""

    def test_full_workflow(self, tmp_path: pathlib.Path) -> None:
        """Test the full workflow from adding classes to rendering."""
        visualizer = EventVisualizer()

        # Add publishers and subscribers
        visualizer.add_publisher(VizUserPublisher)
        visualizer.add_publisher(VizOrderPublisher)
        visualizer.add_subscriber(VizUserSubscriber)
        visualizer.add_subscriber(VizOrderSubscriber)
        visualizer.add_subscriber(VizMultiEventSubscriber)

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

    def test_reusable_visualizer(self, tmp_path: pathlib.Path) -> None:
        """Test that a visualizer can be reused for multiple graphs."""
        visualizer = EventVisualizer()

        # First graph
        visualizer.add_publisher(VizUserPublisher)
        visualizer.add_subscriber(VizUserSubscriber)
        graph1 = visualizer.generate_graph()
        assert graph1 is not None

        # Clear and create second graph
        visualizer.clear()
        visualizer.add_publisher(VizOrderPublisher)
        visualizer.add_subscriber(VizOrderSubscriber)
        graph2 = visualizer.generate_graph()
        assert graph2 is not None

        # Verify graphs are different
        assert "VizUserPublisher" in graph1.source
        assert "VizUserPublisher" not in graph2.source
        assert "VizOrderPublisher" not in graph1.source
        assert "VizOrderPublisher" in graph2.source


class TestVisualizerEdgeCases:
    """Test edge cases for coverage."""

    def test_publisher_with_no_publications(self) -> None:
        """Test that a publisher with no publications shows 'No publications' (line 138)."""

        class EmptyPublisher(MultiPublisher):
            pass

        visualizer = EventVisualizer()
        visualizer.add_publisher(EmptyPublisher)
        graph = visualizer.generate_graph()

        assert "No publications" in graph.source

    def test_subscriber_with_no_subscriptions(self) -> None:
        """Test that a subscriber with no subscriptions shows 'No subscriptions' (line 172)."""

        class EmptySubscriber(MultiSubscriber):
            pass

        visualizer = EventVisualizer()
        visualizer.add_subscriber(EmptySubscriber)
        graph = visualizer.generate_graph()

        assert "No subscriptions" in graph.source

    def test_find_matches_with_invalid_tag(self) -> None:
        """Test that _find_matches skips invalid tags gracefully (lines 242-244)."""
        visualizer = EventVisualizer()
        visualizer.add_publisher(VizUserPublisher)

        publications = visualizer._publishers[VizUserPublisher]

        # Create a subscription with an invalid tag (a type that causes ValueError
        # when passed to EventPublication). We need a tag where EventPublication
        # raises ValueError - that happens when tag is not Enum, str, or int.
        invalid_subscription = EventSubscription(
            VizUserPublisher,
            [3.14],  # type: ignore[list-item]  # float will cause ValueError in EventPublication
            lambda self, event: None,
        )

        subscriptions = {"bad_sub": invalid_subscription}

        # Should not raise, just skip the invalid tag
        matches = visualizer._find_matches(
            VizUserPublisher, publications, subscriptions
        )
        assert isinstance(matches, list)
