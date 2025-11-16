"""
Tests for string-based event tags with deterministic hashing.

These tests verify that string event tags are consistently hashed across
different Python processes and sessions.
"""

import subprocess
import sys

from eventspype.pub.publication import EventPublication


class TestStringEventTagConsistency:
    """Test that string event tags produce consistent hashes."""

    def test_string_tag_normalization(self) -> None:
        """Test that string tags with different cases normalize to the same value."""
        pub1 = EventPublication("user_created", str)
        pub2 = EventPublication("USER_CREATED", str)
        pub3 = EventPublication("User_Created", str)

        assert pub1.event_tag == pub2.event_tag == pub3.event_tag
        assert pub1.original_tag == "user_created"
        assert pub2.original_tag == "USER_CREATED"

    def test_string_tag_deterministic(self) -> None:
        """Test that the same string always produces the same hash."""
        tag1 = EventPublication("test_event", str)
        tag2 = EventPublication("test_event", str)
        tag3 = EventPublication("TEST_EVENT", str)

        assert tag1.event_tag == tag2.event_tag == tag3.event_tag

    def test_different_strings_different_hashes(self) -> None:
        """Test that different strings produce different hashes."""
        pub1 = EventPublication("event_a", str)
        pub2 = EventPublication("event_b", str)
        pub3 = EventPublication("event_c", str)

        # All should be different
        assert pub1.event_tag != pub2.event_tag
        assert pub2.event_tag != pub3.event_tag
        assert pub1.event_tag != pub3.event_tag

    def test_string_tag_cross_process_consistency(self) -> None:
        """Test that string tags are consistent across different Python processes."""
        # Get hash in current process
        pub = EventPublication("cross_process_test", str)
        current_hash = pub.event_tag

        # Run in a subprocess to get a fresh Python interpreter
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
        subprocess_hash = int(result.stdout.strip())

        # Hashes should match across processes
        assert current_hash == subprocess_hash, (
            f"Hash mismatch: current={current_hash}, subprocess={subprocess_hash}. "
            "String event tags must be deterministic across processes."
        )

    def test_string_tag_known_values(self) -> None:
        """Test specific known hash values to ensure consistency."""
        # These values should remain constant across all Python versions and platforms
        # (derived from MD5 hash of the uppercase string)
        test_cases = [
            ("test", 0x033BD94B),
            ("user_created", 0x844FCAE5),
            ("order_placed", 0x7C0EAEF7),
            ("DATA_UPDATED", 0x9D5833CB),
        ]

        for tag_str, expected_hash in test_cases:
            pub = EventPublication(tag_str, str)
            assert pub.event_tag == expected_hash, (
                f"Hash mismatch for '{tag_str}': "
                f"expected {expected_hash:08X}, got {pub.event_tag:08X}"
            )

    def test_string_tag_in_range(self) -> None:
        """Test that string tag hashes are in valid range."""
        pub = EventPublication("any_string", str)
        # Using first 8 hex chars of MD5 gives us 32-bit integers
        assert 0 <= pub.event_tag < 2**32
        assert isinstance(pub.event_tag, int)

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

        # Different strings should produce different hashes
        assert pub1.event_tag != pub2.event_tag

    def test_string_tag_with_spaces(self) -> None:
        """Test that strings with spaces are handled correctly."""
        pub1 = EventPublication("user created", str)
        pub2 = EventPublication("USER CREATED", str)

        # Case insensitive but space-sensitive
        assert pub1.event_tag == pub2.event_tag


class TestStringTagSubscription:
    """Test that string tags work correctly with subscriptions."""

    def test_string_tag_subscription_matching(self) -> None:
        """Test that subscriptions can match publications with string tags."""
        from eventspype.pub.multipublisher import MultiPublisher
        from eventspype.sub.subscription import EventSubscription

        # Create a real publisher class
        class DummyPublisher(MultiPublisher):
            test_event = EventPublication("test_event", str)

        # Create a subscription with a string tag
        subscription = EventSubscription(
            DummyPublisher,
            "test_event",
            lambda self, event: None,
        )

        # Get the event tags
        tags = subscription._get_event_tags("test_event")

        # Create a publication with the same string
        pub = EventPublication("test_event", str)

        # They should match
        assert tags[0] == pub.event_tag

    def test_string_tag_list_subscription(self) -> None:
        """Test that subscriptions with multiple string tags work correctly."""
        from eventspype.pub.multipublisher import MultiPublisher
        from eventspype.sub.subscription import EventSubscription

        # Create a real publisher class
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

        # Create publications
        pub_a = EventPublication("event_a", str)
        pub_b = EventPublication("event_b", str)
        pub_c = EventPublication("event_c", str)

        # All should match
        assert tags[0] == pub_a.event_tag
        assert tags[1] == pub_b.event_tag
        assert tags[2] == pub_c.event_tag
