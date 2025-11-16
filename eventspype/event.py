from enum import Enum

# Type alias for event tags that can be Enum values, integers, or strings
# Strings are automatically hashed to integers for internal use
EventTag = Enum | int | str


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
