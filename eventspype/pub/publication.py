from typing import Any

from eventspype.event import EventTag, NormalizedTag, normalize_event_tag


class EventPublication:
    # Publications can be generated dynamically in volume by downstream code;
    # slots keep them compact. Identity-based hash/eq is unaffected.
    __slots__ = ("original_tag", "event_class", "event_tag", "__weakref__")

    def __init__(self, event_tag: EventTag, event_class: Any) -> None:
        self.original_tag = event_tag
        self.event_class = event_class
        self.event_tag: NormalizedTag = normalize_event_tag(event_tag)
