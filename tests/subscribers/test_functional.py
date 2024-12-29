from eventspype.subscribers.functional import FunctionalEventSubscriber


def test_functional_subscriber_callback() -> None:
    # Track calls to the callback
    calls = []

    def callback(arg: str, event_tag: int, caller: object) -> None:
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
    calls = []

    def callback(arg: str, event_tag: int, caller: object) -> None:
        calls.append((arg, event_tag, caller))

    subscriber = FunctionalEventSubscriber(callback)

    # Test the call operator
    test_arg = "test"
    test_tag = 1
    test_caller = object()

    subscriber(test_arg, test_tag, test_caller)

    assert len(calls) == 1
    assert calls[0] == (test_arg, test_tag, test_caller)
