import hashlib
from enum import Enum

# Type alias for event tags that can be Enum values, integers, or strings
# Strings are automatically hashed to integers for internal use
EventTag = Enum | int | str


def normalize_event_tag(tag: EventTag) -> int:
    """Normalize an event tag to an integer.

    Enums are converted to their value, strings are hashed deterministically
    using MD5 for cross-process consistency, and integers are returned as-is.
    """
    if isinstance(tag, Enum):
        tag = tag.value
    if isinstance(tag, str):
        return int(hashlib.md5(tag.upper().encode("utf-8")).hexdigest()[:8], 16)
    if isinstance(tag, int):
        return tag
    raise ValueError(f"Invalid event tag: {tag}")


class Event:
    """
    Base class for events in the eventspype framework.

    This is a marker class that can be used as a base for custom event types,
    though it's not required. Events can be any Python object, including
    dataclasses, NamedTuples, or plain classes.

    Example:
        @dataclass
        class UserCreatedEvent(Event):
            user_id: int
            username: str
    """

    pass
