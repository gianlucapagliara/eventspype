import collections
import json
import logging
import threading
import weakref
from types import TracebackType
from typing import Any

from eventspype.broker.broker import (
    MessageBroker,
    _drain_pending,
    _make_removal_finalizer,
)
from eventspype.broker.serializer import EventSerializer, JsonEventSerializer
from eventspype.sub.subscriber import EventSubscriber


class RedisBroker(MessageBroker):
    """
    Redis-based message broker using Redis Pub/Sub.

    Requires the `redis` package to be installed: `pip install redis`

    Events are serialized using the provided EventSerializer (defaults to JSON)
    and published to Redis channels. Subscribers on any connected process will
    receive the events.

    Subscribers are held via **weak references**, consistent with
    ``EventPublisher`` and ``LocalBroker``: the caller must keep a strong
    reference to a subscriber for as long as it should remain subscribed.
    When a subscriber is garbage collected it is automatically removed; the
    Redis-side channel subscription is only torn down on an explicit
    :meth:`unsubscribe` or :meth:`close` (the listener simply finds no local
    subscribers in the meantime).

    **Security:** By default, only event classes explicitly registered via
    :meth:`register_event_class` are allowed during deserialization.  This
    prevents arbitrary code execution if an attacker can publish to the Redis
    channel.  Set ``allow_unregistered_classes=True`` to disable this check
    (not recommended for shared Redis deployments).

    Usage:
        import redis
        from eventspype.broker.redis import RedisBroker

        client = redis.Redis(host="localhost", port=6379)
        broker = RedisBroker(client)
        broker.register_event_class(MyEvent)
    """

    def __init__(
        self,
        redis_client: Any,
        serializer: EventSerializer | None = None,
        channel_prefix: str = "eventspype:",
        allow_unregistered_classes: bool = False,
    ) -> None:
        self._redis = redis_client
        self._serializer = serializer or JsonEventSerializer()
        self._channel_prefix = channel_prefix
        self._allow_unregistered_classes = allow_unregistered_classes
        self._pubsub: Any = None
        self._lock = threading.Lock()
        self._subscribers: dict[str, set[weakref.ReferenceType[EventSubscriber]]] = {}
        # Dead refs queued by weakref finalizers, applied under the lock.
        self._pending_removals: collections.deque[
            tuple[str, weakref.ReferenceType[EventSubscriber]]
        ] = collections.deque()
        self._allowed_classes: dict[str, type] = {}
        self._listener_thread: threading.Thread | None = None
        self._logger: logging.Logger | None = None

    @property
    def logger(self) -> logging.Logger:
        if self._logger is None:
            self._logger = logging.getLogger(__name__)
        return self._logger

    # --- Class allowlist for safe deserialization ---

    def register_event_class(self, event_class: type) -> None:
        """Register an event class as safe for deserialization.

        Only registered classes can be instantiated when receiving messages
        from Redis (unless ``allow_unregistered_classes=True``).
        """
        key = f"{event_class.__module__}.{event_class.__qualname__}"
        self._allowed_classes[key] = event_class

    def register_event_classes(self, *event_classes: type) -> None:
        """Register multiple event classes at once."""
        for cls in event_classes:
            self.register_event_class(cls)

    # --- Context manager ---

    def __enter__(self) -> "RedisBroker":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def _prefixed_channel(self, channel: str) -> str:
        return f"{self._channel_prefix}{channel}"

    def publish(
        self, channel: str, event: Any, event_tag: int | str, caller: Any
    ) -> None:
        # Reclaim finalizer-queued dead refs. publish is send-only and does not
        # otherwise touch the subscriber sets, so without this a process that
        # subscribes once to a quiet channel and then only publishes would
        # accumulate dead refs (and leak the channel entry) until a message is
        # received or an explicit (un)subscribe occurs. Gated on a lock-free
        # truthiness check so the common (nothing pending) publish stays cheap.
        if self._pending_removals:
            with self._lock:
                _drain_pending(self._pending_removals, self._subscribers)
        prefixed = self._prefixed_channel(channel)
        payload = self._serializer.serialize(event)
        message = json.dumps(
            {
                "event_tag": event_tag,
                "event_class": type(event).__qualname__,
                "event_module": type(event).__module__,
                "payload": payload.decode("utf-8"),
            }
        )
        self._redis.publish(prefixed, message)

    def subscribe(self, channel: str, subscriber: EventSubscriber) -> None:
        # Build the weakref (and its finalizer) outside the lock; the finalizer
        # only enqueues the dead ref, never locks. Equal refs hash the same, so
        # the set deduplicates.
        subscriber_ref = weakref.ref(
            subscriber, _make_removal_finalizer(self._pending_removals, channel)
        )
        with self._lock:
            _drain_pending(self._pending_removals, self._subscribers)
            is_new_channel = channel not in self._subscribers
            if is_new_channel:
                self._subscribers[channel] = set()
            self._subscribers[channel].add(subscriber_ref)

        if is_new_channel:
            self._ensure_pubsub()
            prefixed = self._prefixed_channel(channel)
            self._pubsub.subscribe(**{prefixed: self._make_handler(channel)})
        self._ensure_listener()

    def unsubscribe(self, channel: str, subscriber: EventSubscriber) -> None:
        with self._lock:
            _drain_pending(self._pending_removals, self._subscribers)
            subscribers = self._subscribers.get(channel)
            if subscribers is None:
                return
            subscribers.discard(weakref.ref(subscriber))
            channel_empty = not subscribers
            if channel_empty:
                del self._subscribers[channel]

        if channel_empty and self._pubsub is not None:
            self._pubsub.unsubscribe(self._prefixed_channel(channel))

    def close(self) -> None:
        """Clean up Redis pubsub resources."""
        if self._pubsub is not None:
            self._pubsub.unsubscribe()
            self._pubsub.close()
            self._pubsub = None
        self._listener_thread = None

    def _ensure_pubsub(self) -> None:
        if self._pubsub is None:
            self._pubsub = self._redis.pubsub()

    def _ensure_listener(self) -> None:
        restarting = (
            self._listener_thread is not None and not self._listener_thread.is_alive()
        )
        if restarting:
            self.logger.warning("Redis listener thread died — restarting.")
        if self._listener_thread is None or restarting:
            self._listener_thread = self._pubsub.run_in_thread(
                sleep_time=0.01, daemon=True
            )

    def _make_handler(self, channel: str) -> Any:
        def handler(message: Any) -> None:
            if message["type"] != "message":
                return

            try:
                data = json.loads(message["data"])
                event_tag = data["event_tag"]
                payload = data["payload"].encode("utf-8")

                # Resolve event class from module path (uses allowlist)
                event_class = self._resolve_class(
                    data["event_module"], data["event_class"]
                )
                event = self._serializer.deserialize(payload, event_class)

                # Snapshot under lock, iterate outside (listener thread)
                with self._lock:
                    _drain_pending(self._pending_removals, self._subscribers)
                    refs = self._subscribers.get(channel)
                    snapshot = tuple(refs) if refs else ()

                for subscriber_ref in snapshot:
                    subscriber = subscriber_ref()
                    if subscriber is None:
                        continue
                    try:
                        # Direct .call dispatch, consistent with LocalBroker
                        subscriber.call(event, event_tag, self)
                    except Exception:
                        self.logger.error(
                            f"Error dispatching event on channel {channel}.",
                            exc_info=True,
                        )
            except Exception:
                self.logger.error(
                    f"Error processing Redis message on channel {channel}. "
                    f"Message dropped (no retry).",
                    exc_info=True,
                )

        return handler

    def _resolve_class(self, module_name: str, qualname: str) -> type:
        """Resolve a class from its module and qualified name.

        When ``allow_unregistered_classes`` is *False* (default), only classes
        previously registered via :meth:`register_event_class` are allowed.
        This prevents arbitrary module imports from untrusted Redis messages.
        """
        key = f"{module_name}.{qualname}"

        # Fast path: check allowlist
        if key in self._allowed_classes:
            return self._allowed_classes[key]

        if not self._allow_unregistered_classes:
            raise ValueError(
                f"Event class '{key}' is not registered. "
                f"Call broker.register_event_class() to allow it, or set "
                f"allow_unregistered_classes=True (not recommended)."
            )

        # Fallback: dynamic import (opted-in via allow_unregistered_classes)
        import importlib

        module = importlib.import_module(module_name)
        obj: Any = module
        for attr in qualname.split("."):
            obj = getattr(obj, attr)
        return obj  # type: ignore[no-any-return]
