import hashlib
from enum import Enum

# Type alias for event tags that can be Enum values, integers, or strings
# Strings are automatically hashed to integers for internal use
EventTag = Enum | int | str


class TagEnum(Enum):
    """Optional base class for event tag enums with value validation.

    Validates at class creation time that all member values are ``int`` or
    ``str`` — the only types accepted by :func:`normalize_event_tag`.  Using
    ``TagEnum`` instead of plain ``Enum`` catches invalid values (e.g.
    ``float``, ``dict``) immediately at import time with a clear error message.

    Example::

        class MyEvents(TagEnum):
            USER_CREATED = 1
            ORDER_PLACED = "order_placed"
    """

    def __new__(cls, value: int | str) -> "TagEnum":
        if not isinstance(value, int | str):
            raise TypeError(
                f"TagEnum member value must be int or str, "
                f"got {type(value).__name__}: {value!r}"
            )
        obj = object.__new__(cls)
        obj._value_ = value
        return obj


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


def format_event_tag(tag: EventTag) -> str:
    """Format an event tag for human-readable display.

    - Enum members: ``"MyEnum.MEMBER_NAME"``
    - Strings: ``'"some_tag"'``
    - Integers: ``"42"``
    """
    if isinstance(tag, Enum):
        return f"{tag.__class__.__name__}.{tag.name}"
    if isinstance(tag, str):
        return f'"{tag}"'
    return str(tag)


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
