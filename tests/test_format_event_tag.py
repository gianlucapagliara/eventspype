"""Tests for the format_event_tag utility function."""

from enum import Enum

from eventspype.event import TagEnum, format_event_tag


class SampleEnum(Enum):
    USER_CREATED = 1
    ORDER_PLACED = 2


class SampleTagEnum(TagEnum):
    ITEM_ADDED = 10
    ITEM_REMOVED = "item_removed"


class TestFormatEventTagEnum:
    def test_enum_member(self) -> None:
        assert format_event_tag(SampleEnum.USER_CREATED) == "SampleEnum.USER_CREATED"

    def test_enum_member_other(self) -> None:
        assert format_event_tag(SampleEnum.ORDER_PLACED) == "SampleEnum.ORDER_PLACED"

    def test_tag_enum_int_member(self) -> None:
        assert format_event_tag(SampleTagEnum.ITEM_ADDED) == "SampleTagEnum.ITEM_ADDED"

    def test_tag_enum_str_member(self) -> None:
        assert (
            format_event_tag(SampleTagEnum.ITEM_REMOVED) == "SampleTagEnum.ITEM_REMOVED"
        )


class TestFormatEventTagString:
    def test_simple_string(self) -> None:
        assert format_event_tag("user_created") == '"user_created"'

    def test_empty_string(self) -> None:
        assert format_event_tag("") == '""'

    def test_string_with_spaces(self) -> None:
        assert format_event_tag("my event") == '"my event"'


class TestFormatEventTagInteger:
    def test_positive_int(self) -> None:
        assert format_event_tag(42) == "42"

    def test_zero(self) -> None:
        assert format_event_tag(0) == "0"

    def test_negative_int(self) -> None:
        assert format_event_tag(-1) == "-1"
