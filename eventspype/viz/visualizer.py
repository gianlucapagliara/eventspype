from eventspype.event import EventTag, format_event_tag, normalize_event_tag
from eventspype.pub.multipublisher import MultiPublisher
from eventspype.pub.publication import EventPublication
from eventspype.sub.multisubscriber import MultiSubscriber
from eventspype.sub.subscription import EventSubscription

try:
    import graphviz
except ImportError as err:
    raise ImportError(
        "graphviz is required for visualization. Install it with: pip install graphviz"
    ) from err


class EventVisualizer:
    """
    Visualizes the event system architecture using graphviz.

    Creates a directed graph showing:
    - Publisher classes with their event publications
    - Subscriber classes with their event subscriptions
    - Connections between publishers and subscribers based on matching event tags
    """

    def __init__(self) -> None:
        """Initialize the EventVisualizer."""
        self._publishers: dict[type[MultiPublisher], dict[str, EventPublication]] = {}
        self._subscribers: dict[
            type[MultiSubscriber], dict[str, EventSubscription]
        ] = {}

    def add_publisher(self, publisher_class: type[MultiPublisher]) -> None:
        """
        Add a publisher class to the visualization.

        Args:
            publisher_class: A MultiPublisher subclass to visualize
        """
        if not issubclass(publisher_class, MultiPublisher):
            raise ValueError("Publisher class must be a subclass of MultiPublisher")

        self._publishers[publisher_class] = publisher_class.get_event_definitions()

    def add_subscriber(self, subscriber_class: type[MultiSubscriber]) -> None:
        """
        Add a subscriber class to the visualization.

        Args:
            subscriber_class: A MultiSubscriber subclass to visualize
        """
        if not issubclass(subscriber_class, MultiSubscriber):
            raise ValueError("Subscriber class must be a subclass of MultiSubscriber")

        self._subscribers[subscriber_class] = subscriber_class.get_event_definitions()

    def generate_graph(
        self,
        graph_name: str = "EventSystem",
        graph_format: str = "png",
    ) -> graphviz.Digraph:
        """
        Generate a graphviz Digraph representing the event system.

        Args:
            graph_name: Name of the graph
            graph_format: Output format (png, pdf, svg, etc.)

        Returns:
            A graphviz.Digraph object
        """
        graph = graphviz.Digraph(
            name=graph_name,
            format=graph_format,
            graph_attr={
                "rankdir": "LR",
                "splines": "ortho",
                "nodesep": "0.8",
                "ranksep": "1.5",
            },
        )

        # Add publisher nodes
        for publisher_class, publications in self._publishers.items():
            self._add_publisher_node(graph, publisher_class, publications)

        # Add subscriber nodes
        for subscriber_class, subscriptions in self._subscribers.items():
            self._add_subscriber_node(graph, subscriber_class, subscriptions)

        # Add edges based on matching event tags
        self._add_edges(graph)

        return graph

    def render(
        self,
        output_path: str,
        graph_name: str = "EventSystem",
        graph_format: str = "png",
        view: bool = False,
    ) -> str:
        """
        Render the graph to a file.

        Args:
            output_path: Path where the output file will be saved (without extension)
            graph_name: Name of the graph
            graph_format: Output format (png, pdf, svg, etc.)
            view: Whether to open the rendered file with the default viewer

        Returns:
            The path to the rendered file
        """
        graph = self.generate_graph(graph_name, graph_format)
        result: str = graph.render(output_path, view=view, cleanup=True)
        return result

    def _add_publisher_node(
        self,
        graph: graphviz.Digraph,
        publisher_class: type[MultiPublisher],
        publications: dict[str, EventPublication],
    ) -> None:
        """Add a publisher node to the graph."""
        node_id = f"pub_{id(publisher_class)}"
        class_name = publisher_class.__name__

        # Build the label with publications
        label_parts = [f"<b>{class_name}</b>", "<i>Publisher</i>", ""]

        if publications:
            label_parts.append("<b>Publications:</b>")
            for name, pub in publications.items():
                tag_str = format_event_tag(pub.original_tag)
                label_parts.append(f"• {name}: {tag_str}")
        else:
            label_parts.append("<i>No publications</i>")

        label = "<br/>".join(label_parts)

        graph.node(
            node_id,
            label=f"<{label}>",
            shape="box",
            style="filled,rounded",
            fillcolor="#E3F2FD",
            color="#1976D2",
            penwidth="2",
        )

    def _add_subscriber_node(
        self,
        graph: graphviz.Digraph,
        subscriber_class: type[MultiSubscriber],
        subscriptions: dict[str, EventSubscription],
    ) -> None:
        """Add a subscriber node to the graph."""
        node_id = f"sub_{id(subscriber_class)}"
        class_name = subscriber_class.__name__

        # Build the label with subscriptions
        label_parts = [f"<b>{class_name}</b>", "<i>Subscriber</i>", ""]

        if subscriptions:
            label_parts.append("<b>Subscriptions:</b>")
            for name, sub in subscriptions.items():
                tag_str = sub.event_tag_str
                pub_class_name = sub.publisher_class.__name__
                label_parts.append(f"• {name}: {tag_str} ({pub_class_name})")
        else:
            label_parts.append("<i>No subscriptions</i>")

        label = "<br/>".join(label_parts)

        graph.node(
            node_id,
            label=f"<{label}>",
            shape="box",
            style="filled,rounded",
            fillcolor="#F3E5F5",
            color="#7B1FA2",
            penwidth="2",
        )

    def _add_edges(self, graph: graphviz.Digraph) -> None:
        """Add edges between publishers and subscribers based on matching event tags."""
        for pub_class, publications in self._publishers.items():
            pub_node_id = f"pub_{id(pub_class)}"

            for sub_class, subscriptions in self._subscribers.items():
                sub_node_id = f"sub_{id(sub_class)}"

                # Find matching event tags
                matches = self._find_matches(pub_class, publications, subscriptions)

                for _pub_name, _sub_name, tag_str in matches:
                    # Create an edge with a label showing the event tag
                    graph.edge(
                        pub_node_id,
                        sub_node_id,
                        label=tag_str,
                        color="#4CAF50",
                        penwidth="2",
                        fontsize="10",
                    )

    def _find_matches(
        self,
        pub_class: type[MultiPublisher],
        publications: dict[str, EventPublication],
        subscriptions: dict[str, EventSubscription],
    ) -> list[tuple[str, str, str]]:
        """
        Find matches between publications and subscriptions.

        Returns:
            List of tuples (publication_name, subscription_name, tag_string)
        """
        matches = []

        for pub_name, publication in publications.items():
            for sub_name, subscription in subscriptions.items():
                # Check if the subscription is for this publisher class
                if not issubclass(pub_class, subscription.publisher_class):
                    continue

                # Get subscription tags
                sub_tags = subscription.event_tag
                if not isinstance(sub_tags, list):
                    sub_tags = [sub_tags]

                # Check if any subscription tag matches the publication tag
                for sub_tag in sub_tags:
                    try:
                        if normalize_event_tag(sub_tag) == publication.event_tag:
                            tag_str = format_event_tag(publication.original_tag)
                            matches.append((pub_name, sub_name, tag_str))
                            break
                    except ValueError:
                        # Skip invalid tags
                        continue

        return matches

    def _format_tag(self, tag: EventTag) -> str:
        """Format an event tag for display.

        Delegates to :func:`eventspype.event.format_event_tag`.
        """
        return format_event_tag(tag)

    def clear(self) -> None:
        """Clear all publishers and subscribers from the visualizer."""
        self._publishers.clear()
        self._subscribers.clear()
