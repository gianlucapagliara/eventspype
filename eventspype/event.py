from enum import Enum

# Type alias for event tags that can be Enum values, integers, or strings
EventTag = Enum | int | str

# The normalized form after resolving Enums and uppercasing strings
NormalizedTag = int | str


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


def normalize_event_tag(tag: EventTag) -> NormalizedTag:
    """Normalize an event tag to its canonical form.

    - Enums use their identity: ``"ClassName.MEMBER_NAME"``.
      Different enum classes with the same value are distinct.
    - Strings are uppercased for case-insensitive matching.
    - Integers are returned as-is.
    """
    if isinstance(tag, Enum):
        return f"{tag.__class__.__name__}.{tag.name}"
    if isinstance(tag, str):
        return tag.upper()
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
