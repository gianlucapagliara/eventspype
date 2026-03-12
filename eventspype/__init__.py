"""
eventspype - A lightweight and type-safe Python framework for building event-driven applications.
"""

from eventspype.broker.broker import MessageBroker
from eventspype.broker.local import LocalBroker
from eventspype.broker.serializer import EventSerializer, JsonEventSerializer
from eventspype.event import Event, EventTag
from eventspype.pub.multipublisher import MultiPublisher
from eventspype.pub.publication import EventPublication
from eventspype.pub.publisher import EventPublisher
from eventspype.sub.functional import FunctionalEventSubscriber
from eventspype.sub.multisubscriber import MultiSubscriber
from eventspype.sub.reporter import ReportingEventSubscriber
from eventspype.sub.subscriber import EventSubscriber, OwnedEventSubscriber
from eventspype.sub.subscription import EventSubscription, PublicationSubscription
from eventspype.sub.tracker import TrackingEventSubscriber
from eventspype.viz.visualizer import EventVisualizer

__all__ = [
    # Core Event Types
    "Event",
    "EventTag",
    # Brokers
    "MessageBroker",
    "LocalBroker",
    "EventSerializer",
    "JsonEventSerializer",
    # Publishers
    "EventPublisher",
    "MultiPublisher",
    "EventPublication",
    # Subscribers
    "EventSubscriber",
    "OwnedEventSubscriber",
    "FunctionalEventSubscriber",
    "MultiSubscriber",
    "ReportingEventSubscriber",
    "TrackingEventSubscriber",
    # Subscriptions
    "EventSubscription",
    "PublicationSubscription",
    # Visualization
    "EventVisualizer",
]
