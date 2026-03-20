import hashlib
from enum import Enum
from typing import Any

from eventspype.event import EventTag


class EventPublication:
    def __init__(self, event_tag: EventTag, event_class: Any) -> None:
        self.original_tag = event_tag
        self.event_class = event_class

        if isinstance(event_tag, Enum):
            event_tag = event_tag.value
        if isinstance(event_tag, str):
            # Use deterministic hash to ensure consistency across Python processes
            event_tag = int(
                hashlib.md5(event_tag.upper().encode("utf-8")).hexdigest()[:8], 16
            )
        if not isinstance(event_tag, int):
            raise ValueError(f"Invalid event tag: {event_tag}")
        self.event_tag: int = event_tag

