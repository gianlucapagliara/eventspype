from typing import Any

from eventspype.event import EventTag, NormalizedTag, normalize_event_tag


class EventPublication:
    def __init__(self, event_tag: EventTag, event_class: Any) -> None:
        self.original_tag = event_tag
        self.event_class = event_class
        self.event_tag: NormalizedTag = normalize_event_tag(event_tag)
