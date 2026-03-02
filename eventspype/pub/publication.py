from typing import Any

from eventspype.event import EventTag, normalize_event_tag


class EventPublication:
    def __init__(self, event_tag: EventTag, event_class: Any) -> None:
        self.original_tag = event_tag
        self.event_class = event_class
        self.event_tag: int = normalize_event_tag(event_tag)

    def __hash__(self) -> int:
        return hash(self.event_tag)
