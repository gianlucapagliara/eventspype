"""
eventspype - A lightweight and type-safe Python framework for building event-driven applications.
"""

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

__all__ = [
    # Core Event Types
    "Event",
    "EventTag",
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
]
