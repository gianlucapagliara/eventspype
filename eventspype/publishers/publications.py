from enum import Enum
from typing import Any


class EventPublication:
    def __init__(self, event_tag: Enum | int | str, event_class: Any) -> None:
        self.original_tag = event_tag
        self.event_class = event_class

        if isinstance(event_tag, Enum):
            event_tag = event_tag.value
        if isinstance(event_tag, str):
            event_tag = hash(event_tag.upper()) % 10**8
        if not isinstance(event_tag, int):
            raise ValueError(f"Invalid event tag: {event_tag}")
        self.event_tag: int = event_tag

    def __hash__(self) -> int:
        return hash((self.event_tag, self.event_class))
