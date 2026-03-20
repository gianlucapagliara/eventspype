from typing import Any

from eventspype.event import EventTag
from eventspype.sub.functional import FunctionalEventSubscriber


def test_functional_subscriber_callback() -> None:
    # Track calls to the callback
    calls: list[Any] = []

    def callback(arg: Any, event_tag: EventTag, caller: Any) -> Any:
        calls.append((arg, event_tag, caller))

    subscriber = FunctionalEventSubscriber(callback)

    # Test the callback
    test_arg = "test"
    test_tag = 1
    test_caller = object()

    subscriber.call(test_arg, test_tag, test_caller)

    assert len(calls) == 1
    assert calls[0] == (test_arg, test_tag, test_caller)


def test_functional_subscriber_call_operator() -> None:
    # Track calls to the callback
    calls: list[Any] = []

    def callback(arg: Any, event_tag: EventTag, caller: Any) -> Any:
        calls.append((arg, event_tag, caller))

    subscriber = FunctionalEventSubscriber(callback)

    # Test the call operator
    test_arg = "test"
    test_tag = 1
    test_caller = object()

    subscriber(test_arg, test_tag, test_caller)

    assert len(calls) == 1
    assert calls[0] == (test_arg, test_tag, test_caller)


def test_functional_subscriber_without_event_info() -> None:
    calls = []

    def callback(arg: str) -> None:
        calls.append(arg)

    subscriber = FunctionalEventSubscriber(callback, with_event_info=False)

    test_arg = "test_value"
    test_tag = 42
    test_caller = object()

    subscriber.call(test_arg, test_tag, test_caller)

    assert len(calls) == 1
    # Should only receive the arg, not tag/caller
    assert calls[0] == test_arg
