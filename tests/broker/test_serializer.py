from dataclasses import dataclass
from typing import Any, NamedTuple

import pytest

from eventspype.broker.serializer import JsonEventSerializer


@dataclass
class SampleEvent:
    user_id: int
    username: str


class SampleNamedTuple(NamedTuple):
    x: int
    y: str


class DictProtocolEvent:
    def __init__(self, value: int) -> None:
        self.value = value

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DictProtocolEvent":
        return cls(**data)


@pytest.fixture
def serializer() -> JsonEventSerializer:
    return JsonEventSerializer()


def test_serialize_dataclass(serializer: JsonEventSerializer) -> None:
    event = SampleEvent(user_id=1, username="alice")
    data = serializer.serialize(event)
    result = serializer.deserialize(data, SampleEvent)

    assert isinstance(result, SampleEvent)
    assert result.user_id == 1
    assert result.username == "alice"


def test_serialize_namedtuple(serializer: JsonEventSerializer) -> None:
    event = SampleNamedTuple(x=42, y="hello")
    data = serializer.serialize(event)
    result = serializer.deserialize(data, SampleNamedTuple)

    assert isinstance(result, SampleNamedTuple)
    assert result.x == 42
    assert result.y == "hello"


def test_serialize_dict_protocol(serializer: JsonEventSerializer) -> None:
    event = DictProtocolEvent(value=99)
    data = serializer.serialize(event)
    result = serializer.deserialize(data, DictProtocolEvent)

    assert isinstance(result, DictProtocolEvent)
    assert result.value == 99


def test_serialize_plain_dict(serializer: JsonEventSerializer) -> None:
    event = {"key": "value", "number": 42}
    data = serializer.serialize(event)
    result = serializer.deserialize(data, dict)

    assert result == {"key": "value", "number": 42}


def test_serialize_primitive(serializer: JsonEventSerializer) -> None:
    data = serializer.serialize("hello")
    result = serializer.deserialize(data, str)
    assert result == "hello"
