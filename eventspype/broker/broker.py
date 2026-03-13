from abc import abstractmethod
from typing import Any

from eventspype.sub.subscriber import EventSubscriber


class MessageBroker:
    """
    Abstract base class for message brokers.

    A message broker is responsible for delivering events from publishers to subscribers.
    The default implementation (LocalBroker) dispatches events in-process, while external
    implementations (e.g. RedisBroker) can route events through external message systems.
    """

    @abstractmethod
    def publish(
        self, channel: str, event: Any, event_tag: int, caller: Any
    ) -> None:
        """Publish an event to a channel.

        Args:
            channel: The channel/topic name to publish to.
            event: The event object to publish.
            event_tag: The integer event tag.
            caller: The publisher that triggered the event.
        """
        raise NotImplementedError

    @abstractmethod
    def subscribe(self, channel: str, subscriber: EventSubscriber) -> None:
        """Subscribe to events on a channel.

        Args:
            channel: The channel/topic name to subscribe to.
            subscriber: The subscriber to receive events.
        """
        raise NotImplementedError

    @abstractmethod
    def unsubscribe(self, channel: str, subscriber: EventSubscriber) -> None:
        """Unsubscribe from events on a channel.

        Args:
            channel: The channel/topic name to unsubscribe from.
            subscriber: The subscriber to remove.
        """
        raise NotImplementedError
