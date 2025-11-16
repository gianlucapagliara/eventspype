"""
Example demonstrating the event visualization functionality.

This example shows how to use the EventVisualizer to create a graphviz diagram
of your event system architecture, displaying publishers, subscribers, and their
connections based on event tags.
"""

from dataclasses import dataclass
from enum import Enum

from eventspype import (
    Event,
    EventPublication,
    EventSubscription,
    EventVisualizer,
    MultiPublisher,
    MultiSubscriber,
)


# Define event tags
class EventTag(Enum):
    USER_CREATED = 1
    USER_UPDATED = 2
    USER_DELETED = 3
    ORDER_PLACED = 4
    ORDER_SHIPPED = 5


# Define event types
@dataclass
class UserCreatedEvent(Event):
    user_id: int
    username: str
    email: str


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
    amount: float


@dataclass
class OrderShippedEvent(Event):
    order_id: int
    tracking_number: str


# Define publishers
class UserPublisher(MultiPublisher):
    """Publisher for user-related events."""

    user_created = EventPublication(EventTag.USER_CREATED, UserCreatedEvent)
    user_updated = EventPublication(EventTag.USER_UPDATED, UserUpdatedEvent)
    user_deleted = EventPublication(EventTag.USER_DELETED, UserDeletedEvent)


class OrderPublisher(MultiPublisher):
    """Publisher for order-related events."""

    order_placed = EventPublication(EventTag.ORDER_PLACED, OrderPlacedEvent)
    order_shipped = EventPublication(EventTag.ORDER_SHIPPED, OrderShippedEvent)


# Define subscribers
class EmailNotificationService(MultiSubscriber):
    """Sends email notifications for various events."""

    on_user_created = EventSubscription(
        UserPublisher,
        EventTag.USER_CREATED,
        lambda self, event: print(f"Sending welcome email to {event.email}"),
    )

    on_order_placed = EventSubscription(
        OrderPublisher,
        EventTag.ORDER_PLACED,
        lambda self, event: print(f"Sending order confirmation for {event.order_id}"),
    )

    on_order_shipped = EventSubscription(
        OrderPublisher,
        EventTag.ORDER_SHIPPED,
        lambda self, event: print(
            f"Sending shipping notification for {event.order_id}"
        ),
    )


class AuditLogService(MultiSubscriber):
    """Logs all user-related events for auditing."""

    on_user_events = EventSubscription(
        UserPublisher,
        [EventTag.USER_CREATED, EventTag.USER_UPDATED, EventTag.USER_DELETED],
        lambda self, event: print(f"Logging event: {event}"),
    )


class AnalyticsService(MultiSubscriber):
    """Tracks analytics for user and order events."""

    on_user_created = EventSubscription(
        UserPublisher,
        EventTag.USER_CREATED,
        lambda self, event: print(f"Analytics: New user {event.user_id}"),
    )

    on_order_placed = EventSubscription(
        OrderPublisher,
        EventTag.ORDER_PLACED,
        lambda self, event: print(f"Analytics: Order placed ${event.amount}"),
    )


def main() -> None:
    """Create and render a visualization of the event system."""
    # Create the visualizer
    visualizer = EventVisualizer()

    # Add publishers
    print("Adding publishers...")
    visualizer.add_publisher(UserPublisher)
    visualizer.add_publisher(OrderPublisher)

    # Add subscribers
    print("Adding subscribers...")
    visualizer.add_subscriber(EmailNotificationService)
    visualizer.add_subscriber(AuditLogService)
    visualizer.add_subscriber(AnalyticsService)

    # Generate and render the graph
    print("Generating visualization...")
    output_path = "event_system_diagram"

    try:
        result = visualizer.render(
            output_path,
            graph_name="EventSystemArchitecture",
            graph_format="png",
            view=False,  # Set to True to automatically open the generated image
        )
        print(f"✓ Visualization saved to: {result}")
        print("\nThe diagram shows:")
        print("  - Blue boxes: Publishers with their event publications")
        print("  - Purple boxes: Subscribers with their event subscriptions")
        print("  - Green arrows: Connections between publishers and subscribers")
    except Exception as e:
        print(f"✗ Error generating visualization: {e}")
        print(
            "\nNote: You may need to install Graphviz system package in addition to the Python package:"
        )
        print("  - macOS: brew install graphviz")
        print("  - Ubuntu/Debian: sudo apt-get install graphviz")
        print("  - Windows: Download from https://graphviz.org/download/")


if __name__ == "__main__":
    main()
