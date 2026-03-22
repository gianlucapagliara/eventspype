from dataclasses import dataclass
from enum import Enum
from typing import Any, NamedTuple

import pytest

from eventspype.broker.serializer import JsonEventSerializer, make_json_safe


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


# --- make_json_safe tests ---


class Color(Enum):
    RED = "red"
    GREEN = "green"


class NestedEnum(Enum):
    INNER = Color.RED


@dataclass
class Point:
    x: int
    y: int


class Coord(NamedTuple):
    lat: float
    lon: float


class TestMakeJsonSafePrimitives:
    def test_none(self) -> None:
        assert make_json_safe(None) is None

    def test_bool(self) -> None:
        assert make_json_safe(True) is True
        assert make_json_safe(False) is False

    def test_int(self) -> None:
        assert make_json_safe(42) == 42

    def test_float(self) -> None:
        assert make_json_safe(3.14) == 3.14

    def test_str(self) -> None:
        assert make_json_safe("hello") == "hello"


class TestMakeJsonSafeEnum:
    def test_enum_value(self) -> None:
        assert make_json_safe(Color.RED) == "red"

    def test_nested_enum_value(self) -> None:
        # Enum whose value is another Enum
        assert make_json_safe(NestedEnum.INNER) == "red"


class TestMakeJsonSafeDataclass:
    def test_dataclass_to_dict(self) -> None:
        result = make_json_safe(Point(x=1, y=2))
        assert result == {"x": 1, "y": 2}


class TestMakeJsonSafeNamedTuple:
    def test_namedtuple_to_dict(self) -> None:
        result = make_json_safe(Coord(lat=1.0, lon=2.0))
        assert result == {"lat": 1.0, "lon": 2.0}


class TestMakeJsonSafeDict:
    def test_non_str_keys(self) -> None:
        result = make_json_safe({1: "a", 2: "b"})
        assert result == {"1": "a", "2": "b"}

    def test_nested_dict_with_enum(self) -> None:
        result = make_json_safe({"color": Color.GREEN, "point": Point(x=3, y=4)})
        assert result == {"color": "green", "point": {"x": 3, "y": 4}}


class TestMakeJsonSafeCollections:
    def test_set_to_list(self) -> None:
        result = make_json_safe({1, 2, 3})
        assert sorted(result) == [1, 2, 3]

    def test_frozenset_to_list(self) -> None:
        result = make_json_safe(frozenset([1, 2]))
        assert sorted(result) == [1, 2]

    def test_tuple_to_list(self) -> None:
        result = make_json_safe((1, 2, 3))
        assert result == [1, 2, 3]

    def test_list_pass_through(self) -> None:
        result = make_json_safe([1, "a", None])
        assert result == [1, "a", None]


class TestMakeJsonSafeFallback:
    def test_unknown_object_to_str(self) -> None:
        class Custom:
            def __str__(self) -> str:
                return "custom_value"

        result = make_json_safe(Custom())
        assert result == "custom_value"
