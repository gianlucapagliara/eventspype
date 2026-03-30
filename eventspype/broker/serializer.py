import dataclasses
import json
from abc import abstractmethod
from enum import Enum
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


def make_json_safe(obj: Any, _seen: set[int] | None = None) -> Any:
    """Recursively convert a value into a JSON-serializable form.

    Tracks object identity to avoid infinite recursion on circular references.
    """
    if obj is None or isinstance(obj, bool | int | float | str):
        return obj

    # Guard against circular references
    obj_id = id(obj)
    if _seen is None:
        _seen = set()
    if obj_id in _seen:
        return f"<circular ref {type(obj).__name__}>"
    _seen.add(obj_id)

    try:
        if isinstance(obj, Enum):
            return make_json_safe(obj.value, _seen)
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return make_json_safe(dataclasses.asdict(obj), _seen)
        if hasattr(obj, "_asdict"):  # NamedTuple
            return make_json_safe(obj._asdict(), _seen)
        if isinstance(obj, dict):
            return {str(k): make_json_safe(v, _seen) for k, v in obj.items()}
        if isinstance(obj, list | tuple | set | frozenset):
            return [make_json_safe(item, _seen) for item in obj]
        return str(obj)
    finally:
        _seen.discard(obj_id)
