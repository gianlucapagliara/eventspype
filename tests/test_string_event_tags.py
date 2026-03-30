"""
Tests for string-based event tags.

These tests verify that string event tags are consistently uppercased
and work correctly across processes and with subscriptions.
"""

import subprocess
import sys

from eventspype.pub.publication import EventPublication


class TestStringEventTagConsistency:
    """Test that string event tags produce consistent normalized values."""

    def test_string_tag_normalization(self) -> None:
        """Test that string tags with different cases normalize to the same value."""
        pub1 = EventPublication("user_created", str)
        pub2 = EventPublication("USER_CREATED", str)
        pub3 = EventPublication("User_Created", str)

        assert pub1.event_tag == pub2.event_tag == pub3.event_tag
        assert pub1.event_tag == "USER_CREATED"
        assert pub1.original_tag == "user_created"
        assert pub2.original_tag == "USER_CREATED"

    def test_string_tag_deterministic(self) -> None:
        """Test that the same string always produces the same normalized tag."""
        tag1 = EventPublication("test_event", str)
        tag2 = EventPublication("test_event", str)
        tag3 = EventPublication("TEST_EVENT", str)

        assert tag1.event_tag == tag2.event_tag == tag3.event_tag

    def test_different_strings_different_tags(self) -> None:
        """Test that different strings produce different tags."""
        pub1 = EventPublication("event_a", str)
        pub2 = EventPublication("event_b", str)
        pub3 = EventPublication("event_c", str)

        assert pub1.event_tag != pub2.event_tag
        assert pub2.event_tag != pub3.event_tag
        assert pub1.event_tag != pub3.event_tag

    def test_string_tag_cross_process_consistency(self) -> None:
        """Test that string tags are consistent across different Python processes."""
        pub = EventPublication("cross_process_test", str)
        current_tag = pub.event_tag

        code = """
import sys
sys.path.insert(0, '.')
from eventspype.pub.publication import EventPublication
pub = EventPublication("cross_process_test", str)
print(pub.event_tag)
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=True,
        )
        subprocess_tag = result.stdout.strip()

        assert current_tag == subprocess_tag, (
            f"Tag mismatch: current={current_tag}, subprocess={subprocess_tag}. "
            "String event tags must be deterministic across processes."
        )

    def test_string_tag_known_values(self) -> None:
        """Test specific known normalized values."""
        test_cases = [
            ("test", "TEST"),
            ("user_created", "USER_CREATED"),
            ("order_placed", "ORDER_PLACED"),
            ("DATA_UPDATED", "DATA_UPDATED"),
        ]

        for tag_str, expected in test_cases:
            pub = EventPublication(tag_str, str)
            assert pub.event_tag == expected

    def test_string_tag_type(self) -> None:
        """Test that string tags stay as strings (not hashed to int)."""
        pub = EventPublication("any_string", str)
        assert isinstance(pub.event_tag, str)

    def test_empty_string_tag(self) -> None:
        """Test that empty strings are handled consistently."""
        pub1 = EventPublication("", str)
        pub2 = EventPublication("", str)
        assert pub1.event_tag == pub2.event_tag

    def test_unicode_string_tags(self) -> None:
        """Test that unicode strings are handled correctly."""
        pub1 = EventPublication("événement", str)
        pub2 = EventPublication("événement", str)
        pub3 = EventPublication("ÉVÉNEMENT", str)

        assert pub1.event_tag == pub2.event_tag == pub3.event_tag

    def test_special_characters_in_string_tags(self) -> None:
        """Test that special characters are handled correctly."""
        pub1 = EventPublication("user.created", str)
        pub2 = EventPublication("user_created", str)

        assert pub1.event_tag != pub2.event_tag

    def test_string_tag_with_spaces(self) -> None:
        """Test that strings with spaces are handled correctly."""
        pub1 = EventPublication("user created", str)
        pub2 = EventPublication("USER CREATED", str)

        assert pub1.event_tag == pub2.event_tag


class TestStringTagSubscription:
    """Test that string tags work correctly with subscriptions."""

    def test_string_tag_subscription_matching(self) -> None:
        """Test that subscriptions can match publications with string tags."""
        from eventspype.pub.multipublisher import MultiPublisher
        from eventspype.sub.subscription import EventSubscription

        class DummyPublisher(MultiPublisher):
            test_event = EventPublication("test_event", str)

        subscription = EventSubscription(
            DummyPublisher,
            "test_event",
            lambda self, event: None,
        )

        tags = subscription._get_event_tags("test_event")
        pub = EventPublication("test_event", str)

        assert tags[0] == pub.event_tag

    def test_string_tag_list_subscription(self) -> None:
        """Test that subscriptions with multiple string tags work correctly."""
        from eventspype.pub.multipublisher import MultiPublisher
        from eventspype.sub.subscription import EventSubscription

        class DummyPublisher(MultiPublisher):
            event_a = EventPublication("event_a", str)
            event_b = EventPublication("event_b", str)
            event_c = EventPublication("event_c", str)

        subscription = EventSubscription(
            DummyPublisher,
            ["event_a", "event_b", "event_c"],
            lambda self, event: None,
        )

        tags = subscription._get_event_tags(["event_a", "event_b", "event_c"])

        pub_a = EventPublication("event_a", str)
        pub_b = EventPublication("event_b", str)
        pub_c = EventPublication("event_c", str)

        assert tags[0] == pub_a.event_tag
        assert tags[1] == pub_b.event_tag
        assert tags[2] == pub_c.event_tag
