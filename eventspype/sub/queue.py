import asyncio
import logging
import threading
import time
from typing import Any

from eventspype.broker.serializer import make_json_safe
from eventspype.sub.subscriber import EventSubscriber


class QueueEventSubscriber(EventSubscriber):
    """Event subscriber that fans out serialized events to async queues.

    Each consumer gets its own ``asyncio.Queue`` via :meth:`subscribe_consumer`.
    When an event is published, :meth:`call` serializes it into a plain dict and
    places it into every registered queue (full queues are skipped with a
    warning log).

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
        # Each consumer queue mapped to the event loop it belongs to (captured
        # in subscribe_consumer). call() runs on the publisher/listener thread
        # and must hand the put off to that loop via call_soon_threadsafe --
        # asyncio.Queue.put_nowait is not thread-safe and a cross-thread call
        # would fail to wake an awaiting consumer (it would hang). A None loop
        # (queue created outside any running loop) falls back to a direct put.
        self._queues: dict[
            asyncio.Queue[dict[str, Any]], asyncio.AbstractEventLoop | None
        ] = {}
        self._lock = threading.Lock()
        self._logger: logging.Logger | None = None

    @property
    def logger(self) -> logging.Logger:
        if self._logger is None:
            self._logger = logging.getLogger(__name__)
        return self._logger

    def call(
        self,
        arg: Any,
        current_event_tag: int | str,
        current_event_caller: Any,
    ) -> None:
        event_dict = self._build_event_dict(
            arg, current_event_tag, current_event_caller
        )

        # Snapshot under lock, iterate outside
        with self._lock:
            targets = list(self._queues.items())

        for queue, loop in targets:
            if loop is not None:
                # Hand the put to the consumer's loop thread; put_nowait there
                # safely wakes an awaiting get(). Scheduling from any thread
                # (including the loop's own) is correct.
                try:
                    loop.call_soon_threadsafe(self._put_nowait, queue, event_dict)
                except RuntimeError:
                    # Consumer's loop is closed; drop the event for it.
                    pass
            else:
                # No loop was captured (queue created outside a running loop);
                # put directly, preserving the original synchronous behavior.
                self._put_nowait(queue, event_dict)

    def _put_nowait(
        self, queue: "asyncio.Queue[dict[str, Any]]", event_dict: dict[str, Any]
    ) -> None:
        """Place an event into a single queue, dropping it if the queue is full.

        Runs on the consumer's loop thread when scheduled via
        call_soon_threadsafe, so put_nowait and the warning log are loop-safe.
        """
        try:
            queue.put_nowait(event_dict)
        except asyncio.QueueFull:
            self.logger.warning(
                "Consumer queue full (max=%d), event dropped: %s",
                self._max_queue_size,
                event_dict.get("event_type", "unknown"),
            )

    def subscribe_consumer(self) -> asyncio.Queue[dict[str, Any]]:
        """Create and register a new consumer queue.

        Should be called from within the asyncio loop that will consume the
        queue; that loop is captured so cross-thread publishers can wake the
        consumer safely. If there is no running loop, events are delivered with
        a direct (synchronous) put instead.
        """
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=self._max_queue_size
        )
        try:
            loop: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        with self._lock:
            self._queues[queue] = loop
        return queue

    def unsubscribe_consumer(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        """Remove a consumer queue. Unknown queues are silently ignored."""
        with self._lock:
            self._queues.pop(queue, None)

    @property
    def consumer_count(self) -> int:
        """Number of currently subscribed consumers."""
        with self._lock:
            return len(self._queues)

    @staticmethod
    def _build_event_dict(event: Any, tag: int | str, caller: Any) -> dict[str, Any]:
        caller_name = getattr(caller, "name", None) or caller.__class__.__name__
        return {
            "event_type": type(event).__qualname__,
            "event_tag": tag,
            "caller": caller_name,
            "timestamp": time.time(),
            "data": make_json_safe(event),
        }
