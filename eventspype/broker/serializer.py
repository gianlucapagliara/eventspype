import dataclasses
import json
from abc import abstractmethod
from typing import Any


class EventSerializer:
    """Abstract base class for event serialization."""

    @abstractmethod
    def serialize(self, event: Any) -> bytes:
        """Serialize an event to bytes."""
        raise NotImplementedError

    @abstractmethod
    def deserialize(self, data: bytes, event_class: type) -> Any:
        """Deserialize bytes back into an event object.

        Args:
            data: The serialized event data.
            event_class: The expected event class to instantiate.
        """
        raise NotImplementedError


class JsonEventSerializer(EventSerializer):
    """JSON-based event serializer.

    Supports dataclasses, NamedTuples, and objects with a `to_dict()`/`from_dict()` protocol.
    For basic types (dict, list, str, int, etc.), they are serialized directly.
    """

    def serialize(self, event: Any) -> bytes:
        data = self._to_dict(event)
        return json.dumps(data).encode("utf-8")

    def deserialize(self, data: bytes, event_class: type) -> Any:
        parsed = json.loads(data.decode("utf-8"))
        return self._from_dict(parsed, event_class)

    def _to_dict(self, event: Any) -> Any:
        if dataclasses.is_dataclass(event) and not isinstance(event, type):
            return dataclasses.asdict(event)
        if hasattr(event, "_asdict"):
            # NamedTuple
            return event._asdict()
        if hasattr(event, "to_dict"):
            return event.to_dict()
        return event

    def _from_dict(self, data: Any, event_class: type) -> Any:
        if dataclasses.is_dataclass(event_class):
            return event_class(**data)
        if hasattr(event_class, "_make"):
            # NamedTuple
            return event_class(**data)
        if hasattr(event_class, "from_dict"):
            return event_class.from_dict(data)
        return data
