import dataclasses
import logging
from typing import Any, Protocol, TypeVar, cast, runtime_checkable

from .subscriber import EventSubscriber


@runtime_checkable
class HasAsDict(Protocol):
    def _asdict(self) -> dict[str, Any]: ...


@runtime_checkable
class HasDataclass(Protocol):
    __dataclass_fields__: dict[str, Any]


T = TypeVar("T")


class ReportingEventSubscriber(EventSubscriber):
    """
    Event subscriber that logs events to a logger.
    """

    _logger: logging.Logger | None = None

    def __init__(self, event_source: str | None = None) -> None:
        super().__init__()
        self.event_source = event_source

    @classmethod
    def logger(cls) -> logging.Logger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def call(
        self,
        event_object: Any,
        current_event_tag: int,
        current_event_caller: Any,
    ) -> None:
        """
        Process and log an event.

        Args:
            event_object: The event object to log
            current_event_tag: The tag of the current event
            current_event_caller: The publisher that triggered the event
        """
        try:
            # Convert event object to dictionary
            if isinstance(event_object, HasDataclass):
                event_dict = dataclasses.asdict(cast(HasDataclass, event_object))
            elif isinstance(event_object, HasAsDict):
                event_dict = event_object._asdict()
            else:
                event_dict = {"value": str(event_object)}

            # Get event name safely
            try:
                event_name = event_object.__class__.__name__
            except (AttributeError, TypeError):
                event_name = "UnknownEvent"

            # Add event metadata
            metadata: dict[str, Any] = {
                "event_name": event_name,
                "event_source": self.event_source,
                "event_tag": current_event_tag,
            }
            event_dict.update(metadata)

            # Log the event at INFO level
            self.logger().info(
                f"Event received: {event_dict}", extra={"event_data": event_dict}
            )
        except Exception:
            self.logger().error(
                "Error logging event.",
                exc_info=True,
                extra={"event_source": self.event_source},
            )
