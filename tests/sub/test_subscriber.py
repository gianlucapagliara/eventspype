import pytest

from eventspype.sub.subscriber import EventSubscriber, OwnedEventSubscriber


class TestEventSubscriber:
    def test_base_subscriber_call_raises_not_implemented(self) -> None:
        subscriber = EventSubscriber()  # type: ignore[abstract]
        with pytest.raises(NotImplementedError):
            subscriber.call(None, 1, None)

    def test_base_subscriber_call_operator(self) -> None:
        subscriber = EventSubscriber()  # type: ignore[abstract]
        with pytest.raises(NotImplementedError):
            subscriber(None, 1, None)


class TestOwnedEventSubscriber:
    def test_owned_subscriber_initialization(self) -> None:
        owner = object()
        subscriber = OwnedEventSubscriber(owner)  # type: ignore[abstract]
        assert subscriber.owner == owner

    def test_owned_subscriber_call_raises_not_implemented(self) -> None:
        owner = object()
        subscriber = OwnedEventSubscriber(owner)  # type: ignore[abstract]
        with pytest.raises(NotImplementedError):
            subscriber.call(None, 1, None)
