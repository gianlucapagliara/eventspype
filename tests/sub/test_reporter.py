from collections.abc import Generator
from dataclasses import dataclass
from typing import Any, NamedTuple
from unittest.mock import MagicMock, patch

import pytest

from eventspype.sub.reporter import ReportingEventSubscriber


@dataclass
class DataclassEvent:
    message: str
    value: int


class NamedTupleEvent(NamedTuple):
    message: str
    value: int


class SimpleEvent:
    def __init__(self, message: str, value: int) -> None:
        self.message = message
        self.value = value


@pytest.fixture
def reporter() -> ReportingEventSubscriber:
    return ReportingEventSubscriber(event_source="test_source")


@pytest.fixture
def mock_logger() -> Generator[MagicMock, None, None]:
    # Reset the class-level logger before each test
    ReportingEventSubscriber._logger = None
    with patch("logging.getLogger") as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        yield mock_logger


def test_reporter_initialization() -> None:
    # Test with event source
    reporter = ReportingEventSubscriber(event_source="test_source")
    assert reporter.event_source == "test_source"

    # Test without event source
    reporter = ReportingEventSubscriber()
    assert reporter.event_source is None


def test_logger_singleton() -> None:
    # Test that logger is created only once
    reporter1 = ReportingEventSubscriber()
    reporter2 = ReportingEventSubscriber()
    assert reporter1.logger() is reporter2.logger()


def test_dataclass_event_logging(
    reporter: ReportingEventSubscriber, mock_logger: MagicMock
) -> None:
    event = DataclassEvent(message="test message", value=42)
    reporter.call(event, 1, None)

    mock_logger.info.assert_called_once()
    log_message = mock_logger.info.call_args[0][0]
    log_extra = mock_logger.info.call_args[1]["extra"]

    assert "test message" in log_message
    assert log_extra["event_data"]["message"] == "test message"
    assert log_extra["event_data"]["value"] == 42
    assert log_extra["event_data"]["event_name"] == "DataclassEvent"
    assert log_extra["event_data"]["event_source"] == "test_source"
    assert log_extra["event_data"]["event_tag"] == 1


def test_namedtuple_event_logging(
    reporter: ReportingEventSubscriber, mock_logger: MagicMock
) -> None:
    event = NamedTupleEvent(message="test message", value=42)
    reporter.call(event, 1, None)

    mock_logger.info.assert_called_once()
    log_message = mock_logger.info.call_args[0][0]
    log_extra = mock_logger.info.call_args[1]["extra"]

    assert "test message" in log_message
    assert log_extra["event_data"]["message"] == "test message"
    assert log_extra["event_data"]["value"] == 42
    assert log_extra["event_data"]["event_name"] == "NamedTupleEvent"
    assert log_extra["event_data"]["event_source"] == "test_source"
    assert log_extra["event_data"]["event_tag"] == 1


def test_simple_object_logging(
    reporter: ReportingEventSubscriber, mock_logger: MagicMock
) -> None:
    event = SimpleEvent(message="test message", value=42)
    reporter.call(event, 1, None)

    mock_logger.info.assert_called_once()
    log_message = mock_logger.info.call_args[0][0]
    log_extra = mock_logger.info.call_args[1]["extra"]

    assert "SimpleEvent" in log_message
    assert log_extra["event_data"]["value"] == str(event)
    assert log_extra["event_data"]["event_name"] == "SimpleEvent"
    assert log_extra["event_data"]["event_source"] == "test_source"
    assert log_extra["event_data"]["event_tag"] == 1


def test_primitive_value_logging(
    reporter: ReportingEventSubscriber, mock_logger: MagicMock
) -> None:
    event = "test message"
    reporter.call(event, 1, None)

    mock_logger.info.assert_called_once()
    log_message = mock_logger.info.call_args[0][0]
    log_extra = mock_logger.info.call_args[1]["extra"]

    assert "test message" in log_message
    assert log_extra["event_data"]["value"] == "test message"
    assert log_extra["event_data"]["event_name"] == "str"
    assert log_extra["event_data"]["event_source"] == "test_source"
    assert log_extra["event_data"]["event_tag"] == 1


def test_error_handling(
    reporter: ReportingEventSubscriber, mock_logger: MagicMock
) -> None:
    # Create an event that will raise an exception when processed
    class ErrorEvent:
        @property
        def __class__(self) -> Any:
            raise RuntimeError("Test error")

    event = ErrorEvent()
    reporter.call(event, 1, None)

    # Verify that error was collected
    mock_logger.error.assert_called_once_with(
        "Error logging event.",
        exc_info=True,
        extra={"event_source": "test_source"},
    )


def test_none_event_logging(
    reporter: ReportingEventSubscriber, mock_logger: MagicMock
) -> None:
    reporter.call(None, 1, None)

    mock_logger.info.assert_called_once()
    log_message = mock_logger.info.call_args[0][0]
    log_extra = mock_logger.info.call_args[1]["extra"]

    assert "None" in log_message
    assert log_extra["event_data"]["value"] == "None"
    assert log_extra["event_data"]["event_name"] == "NoneType"
    assert log_extra["event_data"]["event_source"] == "test_source"
    assert log_extra["event_data"]["event_tag"] == 1
