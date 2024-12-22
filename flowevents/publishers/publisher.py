import logging
import random
import weakref
from typing import Any

from ..subscribers.subscriber import EventSubscriber
from .publications import EventPublication


class EventPublisher:
    """
    EventPublisher with weak references for a single event type. This avoids the lapsed listener problem by periodically
    performing GC on dead event listeners.

    Dead listener cleanup is done by calling _remove_dead_listeners(), which checks whether the listener weak references are
    alive or not, and removes the dead ones. Each call to _remove_dead_listeners() takes O(n).
    """

    ADD_LISTENER_GC_PROBABILITY = 0.005

    def __init__(self, publication: EventPublication) -> None:
        self._publication = publication
        self._listeners: set[weakref.ReferenceType[EventSubscriber]] = set()
        self._logger: logging.Logger | None = None

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @property
    def logger(self) -> logging.Logger:
        if self._logger is None:
            self._logger = logging.getLogger(__name__)
        return self._logger

    def add_listener(self, listener: EventSubscriber) -> None:
        """Add a listener for this publisher's event."""
        # Create weak reference to the listener
        listener_ref = weakref.ref(listener)
        self._listeners.add(listener_ref)

        # Randomly perform garbage collection
        if random.random() < self.ADD_LISTENER_GC_PROBABILITY:
            self._remove_dead_listeners()

    def remove_listener(self, listener: EventSubscriber) -> None:
        """Remove a listener."""
        # Create a temporary weak reference for comparison
        listener_ref = weakref.ref(listener)

        # Remove the listener if it exists
        self._listeners.discard(listener_ref)

        # Clean up dead listeners
        self._remove_dead_listeners()

    def get_listeners(self) -> list[EventSubscriber]:
        """Get all active listeners."""
        self._remove_dead_listeners()

        # Return only the listeners that are still alive
        return [
            listener
            for listener in (ref() for ref in self._listeners)
            if listener is not None
        ]

    def trigger_event(self, message: Any) -> None:
        """Trigger an event, notifying all listeners with the given message."""
        # Validate event type
        if not isinstance(message, self._publication.event_class):
            raise ValueError(
                f"Invalid event type: expected {self._publication.event_class}, got {type(message)}"
            )

        self._remove_dead_listeners()

        # Make a copy of the listeners to avoid modification during iteration
        listeners = self._listeners.copy()

        for listener_ref in listeners:
            listener = listener_ref()
            if listener is None:
                continue

            try:
                listener(message, self._publication.event_tag, self)
            except Exception:
                self._log_exception(message)

    def _remove_dead_listeners(self) -> None:
        """Remove any dead listeners."""
        # Remove any dead references
        self._listeners = {ref for ref in self._listeners if ref() is not None}

    def _log_exception(self, arg: Any) -> None:
        """Log any exceptions that occur during event processing."""
        self.logger.error(
            f"Unexpected error while processing event {self._publication.event_tag}.",
            exc_info=True,
        )
