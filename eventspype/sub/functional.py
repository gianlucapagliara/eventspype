from collections.abc import Callable
from typing import Any, cast

from eventspype.event import EventTag
from eventspype.sub.subscriber import EventSubscriber

CompleteEventCallback = Callable[[Any, EventTag, Any], Any]
SimpleEventCallback = Callable[[Any], Any]
FunctionalEventCallback = SimpleEventCallback | CompleteEventCallback


class FunctionalEventSubscriber(EventSubscriber):
    def __init__(
        self, callback: FunctionalEventCallback, with_event_info: bool = True
    ) -> None:
        super().__init__()

        if with_event_info:
            self._callback = cast(CompleteEventCallback, callback)
        else:

            def callback_wrapper(
                arg: Any, current_event_tag: EventTag, current_event_caller: Any
            ) -> None:
                callback(arg)  # type: ignore

            self._callback = callback_wrapper

    def call(
        self, arg: Any, current_event_tag: EventTag, current_event_caller: Any
    ) -> None:
        self._callback(arg, current_event_tag, current_event_caller)
