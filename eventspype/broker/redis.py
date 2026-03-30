import json
import logging
import threading
from types import TracebackType
from typing import Any

from eventspype.broker.broker import MessageBroker
from eventspype.broker.serializer import EventSerializer, JsonEventSerializer
from eventspype.sub.subscriber import EventSubscriber


class RedisBroker(MessageBroker):
    """
    Redis-based message broker using Redis Pub/Sub.

    Requires the `redis` package to be installed: `pip install redis`

    Events are serialized using the provided EventSerializer (defaults to JSON)
    and published to Redis channels. Subscribers on any connected process will
    receive the events.

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
        self._subscribers: dict[str, list[EventSubscriber]] = {}
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

    def publish(self, channel: str, event: Any, event_tag: int, caller: Any) -> None:
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
        if channel not in self._subscribers:
            self._subscribers[channel] = []
            self._ensure_pubsub()
            prefixed = self._prefixed_channel(channel)
            self._pubsub.subscribe(**{prefixed: self._make_handler(channel)})

        # Prevent duplicate subscribers
        if subscriber not in self._subscribers[channel]:
            self._subscribers[channel].append(subscriber)
        self._ensure_listener()

    def unsubscribe(self, channel: str, subscriber: EventSubscriber) -> None:
        if channel not in self._subscribers:
            return

        self._subscribers[channel] = [
            s for s in self._subscribers[channel] if s is not subscriber
        ]

        if not self._subscribers[channel]:
            prefixed = self._prefixed_channel(channel)
            if self._pubsub is not None:
                self._pubsub.unsubscribe(prefixed)
            del self._subscribers[channel]

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

                for subscriber in self._subscribers.get(channel, []):
                    try:
                        subscriber(event, event_tag, self)
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
