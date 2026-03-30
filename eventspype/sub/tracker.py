import asyncio
import threading
from collections import deque
from collections.abc import MutableSet
from typing import Any

from async_timeout import timeout

from eventspype.sub.subscriber import EventSubscriber


class TrackingEventSubscriber(EventSubscriber):
    """
    A subscriber that collects events and provides async waiting functionality.

    Thread safety: a ``threading.Lock`` protects internal state so that
    :meth:`call` (publisher thread) and :meth:`wait_for` (asyncio loop)
    can be used concurrently.
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
        self._max_len = max_len
        self._lock = threading.Lock()
        self._generic_collected_events: deque[Any] = deque(maxlen=max_len)
        self._collected_events: dict[type[Any], deque[Any]] = {}
        self._waiting_by_type: dict[type[Any], MutableSet[asyncio.Event]] = {}
        self._wait_returns: dict[asyncio.Event, Any] = {}

    @property
    def event_log(self) -> list[Any]:
        """Get all collected events as a list."""
        with self._lock:
            return list(self._generic_collected_events)

    @property
    def event_source(self) -> str | None:
        """Get the event source identifier."""
        return self._event_source

    def track_event_type(self, event_type: type[Any]) -> None:
        """Register an event type for per-type collection with bounded storage.

        Events of this type will be stored in a dedicated deque (bounded by
        ``max_len``) instead of the generic collection.
        """
        with self._lock:
            if event_type not in self._collected_events:
                self._collected_events[event_type] = deque(maxlen=self._max_len)

    def clear(self) -> None:
        """Clear all collected events."""
        with self._lock:
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
        with self._lock:
            if event_type not in self._waiting_by_type:
                self._waiting_by_type[event_type] = set()
            self._waiting_by_type[event_type].add(notifier)

        try:
            async with timeout(timeout_seconds):
                await notifier.wait()

            with self._lock:
                retval = self._wait_returns.pop(notifier, None)
            return retval
        finally:
            # Always clean up, even on timeout
            with self._lock:
                waiters = self._waiting_by_type.get(event_type)
                if waiters is not None:
                    waiters.discard(notifier)
                    if not waiters:
                        del self._waiting_by_type[event_type]
                self._wait_returns.pop(notifier, None)

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
        with self._lock:
            # Get the appropriate deque for this event type (bounded)
            event_type = type(event_object)
            event_deque = self._collected_events.get(event_type)
            if event_deque is None:
                event_deque = self._generic_collected_events

            # Log the event
            event_deque.append(event_object)

            # Notify waiters for this event type — O(1) lookup by type
            waiters = self._waiting_by_type.get(event_type)
            if waiters:
                for notifier in waiters:
                    self._wait_returns[notifier] = event_object
                    notifier.set()
