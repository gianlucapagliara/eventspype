import asyncio
from collections import deque
from typing import Any

from async_timeout import timeout

from eventspype.sub.subscriber import EventSubscriber


class TrackingEventSubscriber(EventSubscriber):
    """
    A subscriber that collects events and provides async waiting functionality.
    """

    def __init__(self, event_source: str | None = None, max_len: int = 50) -> None:
        """
        Initialize the event logger.

        Args:
            event_source: Optional source identifier for the events
            max_len: Maximum number of events to keep in the log (default: 50)
        """
        super().__init__()
        self._event_source = event_source
        self._generic_collected_events: deque[Any] = deque(maxlen=max_len)
        self._collected_events: dict[type[Any], deque[Any]] = {}
        self._waiting: dict[asyncio.Event, type[Any]] = {}
        self._wait_returns: dict[asyncio.Event, Any] = {}

    @property
    def event_log(self) -> list[Any]:
        """Get all collected events as a list."""
        return list(self._generic_collected_events)

    @property
    def event_source(self) -> str | None:
        """Get the event source identifier."""
        return self._event_source

    def clear(self) -> None:
        """Clear all collected events."""
        self._generic_collected_events.clear()
        self._collected_events.clear()

    async def wait_for(
        self, event_type: type[Any], timeout_seconds: float = 180
    ) -> Any:
        """
        Wait for an event of a specific type to occur.

        Args:
            event_type: The type of event to wait for
            timeout_seconds: How long to wait before timing out (default: 180 seconds)

        Returns:
            The event object when it occurs

        Raises:
            TimeoutError: If the event doesn't occur within timeout_seconds
        """
        notifier = asyncio.Event()
        self._waiting[notifier] = event_type

        try:
            async with timeout(timeout_seconds):
                await notifier.wait()

            retval = self._wait_returns.get(notifier)
            if notifier in self._wait_returns:
                del self._wait_returns[notifier]
            return retval
        finally:
            # Always clean up, even on timeout
            if notifier in self._waiting:
                del self._waiting[notifier]
            if notifier in self._wait_returns:
                del self._wait_returns[notifier]

    def call(
        self,
        event_object: Any,
        current_event_tag: int,
        current_event_caller: Any,
    ) -> None:
        """
        Process an event by logging it and notifying any waiters.

        Args:
            event_object: The event to process
            current_event_tag: The tag of the current event
            current_event_caller: The publisher that triggered the event
        """
        # Get the appropriate deque for this event type
        event_type = type(event_object)
        event_deque = self._collected_events.get(event_type)
        if event_deque is None:
            event_deque = self._generic_collected_events

        # Log the event
        event_deque.append(event_object)

        # Notify any waiters for this event type
        should_notify = []
        for notifier, waiting_event_type in self._waiting.items():
            if event_type is waiting_event_type:
                should_notify.append(notifier)
                self._wait_returns[notifier] = event_object

        # Set the events after collecting them all
        for notifier in should_notify:
            notifier.set()
