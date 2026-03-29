"""Tests for the TagEnum base class."""

from enum import Enum

import pytest

from eventspype.event import TagEnum, normalize_event_tag
from eventspype.pub.publication import EventPublication


class IntTagEnum(TagEnum):
    EVENT_A = 1
    EVENT_B = 2


class StrTagEnum(TagEnum):
    USER_CREATED = "user_created"
    ORDER_PLACED = "order_placed"


class MixedTagEnum(TagEnum):
    INT_EVENT = 10
    STR_EVENT = "some_event"


class TestTagEnumValidValues:
    def test_int_values(self) -> None:
        assert IntTagEnum.EVENT_A.value == 1
        assert IntTagEnum.EVENT_B.value == 2

    def test_str_values(self) -> None:
        assert StrTagEnum.USER_CREATED.value == "user_created"
        assert StrTagEnum.ORDER_PLACED.value == "order_placed"

    def test_mixed_values(self) -> None:
        assert MixedTagEnum.INT_EVENT.value == 10
        assert MixedTagEnum.STR_EVENT.value == "some_event"

    def test_is_enum(self) -> None:
        assert isinstance(IntTagEnum.EVENT_A, Enum)
        assert isinstance(StrTagEnum.USER_CREATED, Enum)
        assert isinstance(MixedTagEnum.INT_EVENT, TagEnum)


class TestTagEnumInvalidValues:
    def test_float_value_raises(self) -> None:
        with pytest.raises(TypeError, match="must be int or str"):

            class BadEnum(TagEnum):
                BAD = 3.14  # type: ignore[assignment]

    def test_dict_value_raises(self) -> None:
        with pytest.raises(TypeError, match="must be int or str"):

            class BadEnum(TagEnum):
                BAD = {"key": "val"}  # type: ignore[assignment]

    def test_list_value_raises(self) -> None:
        with pytest.raises(TypeError, match="must be int or str"):

            class BadEnum(TagEnum):
                BAD = [1, 2]  # type: ignore[assignment]

    def test_none_value_raises(self) -> None:
        with pytest.raises(TypeError, match="must be int or str"):

            class BadEnum(TagEnum):
                BAD = None  # type: ignore[assignment]

    def test_bool_value_raises(self) -> None:
        """bool is a subclass of int, so it should be accepted."""

        # This should NOT raise — bool is a subclass of int in Python
        class BoolEnum(TagEnum):
            TRUE_EVENT = True
            FALSE_EVENT = False

        assert BoolEnum.TRUE_EVENT.value is True


class TestTagEnumNormalization:
    def test_int_tag_normalizes(self) -> None:
        assert normalize_event_tag(IntTagEnum.EVENT_A) == 1
        assert normalize_event_tag(IntTagEnum.EVENT_B) == 2

    def test_str_tag_normalizes(self) -> None:
        result = normalize_event_tag(StrTagEnum.USER_CREATED)
        assert isinstance(result, int)
        # Should match direct string normalization
        assert result == normalize_event_tag("user_created")

    def test_mixed_tag_normalizes(self) -> None:
        assert normalize_event_tag(MixedTagEnum.INT_EVENT) == 10
        str_result = normalize_event_tag(MixedTagEnum.STR_EVENT)
        assert str_result == normalize_event_tag("some_event")


class TestTagEnumWithPublication:
    def test_int_tag_publication(self) -> None:
        pub = EventPublication(IntTagEnum.EVENT_A, str)
        assert pub.event_tag == 1
        assert pub.original_tag is IntTagEnum.EVENT_A

    def test_str_tag_publication(self) -> None:
        pub = EventPublication(StrTagEnum.USER_CREATED, str)
        assert isinstance(pub.event_tag, int)
        assert pub.original_tag is StrTagEnum.USER_CREATED

    def test_matches_plain_enum(self) -> None:
        """TagEnum publications should match equivalent plain Enum publications."""

        class PlainEnum(Enum):
            EVENT_A = 1

        pub_tag = EventPublication(IntTagEnum.EVENT_A, str)
        pub_plain = EventPublication(PlainEnum.EVENT_A, str)
        assert pub_tag.event_tag == pub_plain.event_tag
