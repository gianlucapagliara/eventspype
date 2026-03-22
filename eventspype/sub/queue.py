import asyncio
import threading
import time
from typing import Any

from eventspype.broker.serializer import make_json_safe
from eventspype.sub.subscriber import EventSubscriber


class QueueEventSubscriber(EventSubscriber):
    """Event subscriber that fans out serialized events to async queues.

    Each consumer gets its own ``asyncio.Queue`` via :meth:`subscribe_consumer`.
    When an event is published, :meth:`call` serializes it into a plain dict and
    places it into every registered queue (full queues are silently skipped).

    .. note::
        ``EventPublisher`` holds a **weak reference** to its subscribers.
        The caller must keep a strong reference to this object for as long as
        it should remain subscribed.

    Thread safety: a ``threading.Lock`` protects the internal queue list so
    that ``call`` (publisher thread) and ``subscribe_consumer`` /
    ``unsubscribe_consumer`` (asyncio loop) can be used concurrently.
    """

    def __init__(self, max_queue_size: int = 1000) -> None:
        super().__init__()
        self._max_queue_size = max_queue_size
        self._queues: list[asyncio.Queue[dict[str, Any]]] = []
        self._lock = threading.Lock()

    def call(
        self,
        arg: Any,
        current_event_tag: int,
        current_event_caller: Any,
    ) -> None:
        event_dict = self._build_event_dict(
            arg, current_event_tag, current_event_caller
        )

        # Snapshot under lock, iterate outside
        with self._lock:
            queues = list(self._queues)

        for queue in queues:
            try:
                queue.put_nowait(event_dict)
            except asyncio.QueueFull:
                pass

    def subscribe_consumer(self) -> asyncio.Queue[dict[str, Any]]:
        """Create and register a new consumer queue."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=self._max_queue_size
        )
        with self._lock:
            self._queues.append(queue)
        return queue

    def unsubscribe_consumer(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        """Remove a consumer queue. Unknown queues are silently ignored."""
        with self._lock:
            try:
                self._queues.remove(queue)
            except ValueError:
                pass

    @property
    def consumer_count(self) -> int:
        """Number of currently subscribed consumers."""
        with self._lock:
            return len(self._queues)

    @staticmethod
    def _build_event_dict(event: Any, tag: int, caller: Any) -> dict[str, Any]:
        caller_name = getattr(caller, "name", None) or caller.__class__.__name__
        return {
            "event_type": type(event).__qualname__,
            "event_tag": tag,
            "caller": caller_name,
            "timestamp": time.time(),
            "data": make_json_safe(event),
        }
