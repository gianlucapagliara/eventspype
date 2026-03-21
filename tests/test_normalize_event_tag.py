"""
Tests for the normalize_event_tag() utility function.

Verifies that the shared tag normalization logic correctly handles
Enum values, integers, and strings — and matches the behavior
previously duplicated across EventPublication and EventSubscription.
"""

from enum import Enum

import pytest

from eventspype.event import normalize_event_tag
from eventspype.pub.publication import EventPublication


class SampleEvents(Enum):
    EVENT_A = 10
    EVENT_B = 20


class StringEnum(Enum):
    EVENT_X = "my_event"


class TestNormalizeEventTagIntegers:
    def test_integer_passthrough(self) -> None:
        assert normalize_event_tag(1) == 1
        assert normalize_event_tag(0) == 0
        assert normalize_event_tag(999999) == 999999

    def test_negative_integer(self) -> None:
        assert normalize_event_tag(-1) == -1


class TestNormalizeEventTagEnums:
    def test_enum_with_int_value(self) -> None:
        assert normalize_event_tag(SampleEvents.EVENT_A) == 10
        assert normalize_event_tag(SampleEvents.EVENT_B) == 20

    def test_enum_with_string_value(self) -> None:
        """Enum with string value should hash the string."""
        result = normalize_event_tag(StringEnum.EVENT_X)
        assert isinstance(result, int)
        # Should match what EventPublication produces
        pub = EventPublication(StringEnum.EVENT_X, str)
        assert result == pub.event_tag


class TestNormalizeEventTagStrings:
    def test_string_produces_int(self) -> None:
        result = normalize_event_tag("test_event")
        assert isinstance(result, int)

    def test_case_insensitive(self) -> None:
        """Different cases of the same string should produce the same tag."""
        assert normalize_event_tag("hello") == normalize_event_tag("HELLO")
        assert normalize_event_tag("MiXeD") == normalize_event_tag("mixed")

    def test_different_strings_differ(self) -> None:
        assert normalize_event_tag("foo") != normalize_event_tag("bar")

    def test_empty_string(self) -> None:
        result = normalize_event_tag("")
        assert isinstance(result, int)
        # Should be consistent
        assert normalize_event_tag("") == normalize_event_tag("")

    def test_unicode_string(self) -> None:
        result = normalize_event_tag("événement")
        assert isinstance(result, int)
        assert result == normalize_event_tag("ÉVÉNEMENT")

    def test_32bit_range(self) -> None:
        """String tags should produce 32-bit integers (first 8 hex chars of MD5)."""
        result = normalize_event_tag("any_string")
        assert 0 <= result < 2**32

    def test_matches_publication(self) -> None:
        """normalize_event_tag should produce the same result as EventPublication."""
        for tag_str in ["test", "user_created", "order_placed"]:
            pub = EventPublication(tag_str, str)
            assert normalize_event_tag(tag_str) == pub.event_tag


class TestNormalizeEventTagInvalid:
    def test_float_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid event tag"):
            normalize_event_tag(3.14)  # type: ignore[arg-type]

    def test_none_raises(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            normalize_event_tag(None)  # type: ignore[arg-type]

    def test_list_raises(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            normalize_event_tag([1, 2])  # type: ignore[arg-type]
