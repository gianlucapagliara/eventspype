"""
Tests for @cache optimizations on get_event_definitions() and _valid_publications().

Verifies that:
- Cached results are correct and consistent with uncached behavior
- Each subclass gets its own cached result (no cross-class contamination)
- The frozenset cache in _valid_publications() works for O(1) membership checks
"""

import logging
from dataclasses import dataclass
from enum import Enum
from functools import partial
from typing import Any

import pytest

from eventspype.pub.multipublisher import MultiPublisher
from eventspype.pub.publication import EventPublication
from eventspype.pub.publisher import EventPublisher
from eventspype.sub.multisubscriber import MultiSubscriber
from eventspype.sub.subscription import EventSubscription


class Events(Enum):
    A = 1
    B = 2
    C = 3


@dataclass
class EventA:
    data: str


@dataclass
class EventB:
    data: str


@dataclass
class EventC:
    data: str


# --- MultiPublisher caching tests ---


class PublisherBase(MultiPublisher):
    event_a = EventPublication(Events.A, EventA)


class PublisherChild(PublisherBase):
    event_b = EventPublication(Events.B, EventB)


class PublisherGrandchild(PublisherChild):
    event_c = EventPublication(Events.C, EventC)


class TestMultiPublisherGetEventDefinitionsCache:
    def test_returns_correct_definitions(self) -> None:
        defs = PublisherBase.get_event_definitions()
        assert len(defs) == 1
        assert "event_a" in defs

    def test_returns_same_object_on_repeated_calls(self) -> None:
        """@cache should return the exact same dict object."""
        defs1 = PublisherBase.get_event_definitions()
        defs2 = PublisherBase.get_event_definitions()
        assert defs1 is defs2

    def test_subclass_gets_own_cache(self) -> None:
        """Each subclass should have its own cached definitions."""
        base_defs = PublisherBase.get_event_definitions()
        child_defs = PublisherChild.get_event_definitions()
        grandchild_defs = PublisherGrandchild.get_event_definitions()

        assert len(base_defs) == 1
        assert len(child_defs) == 2
        assert len(grandchild_defs) == 3

        # They must be distinct objects
        assert base_defs is not child_defs
        assert child_defs is not grandchild_defs

    def test_inheritance_precedence_with_cache(self) -> None:
        """Child class overrides should take precedence even with caching."""

        class OverridingChild(PublisherBase):
            event_a = EventPublication(
                Events.A, EventB
            )  # Override with different class

        defs = OverridingChild.get_event_definitions()
        assert defs["event_a"].event_class == EventB

    def test_cache_does_not_include_non_publication_attrs(self) -> None:
        class WithMixedAttrs(MultiPublisher):
            event_a = EventPublication(Events.A, EventA)
            not_a_pub = "some string"
            also_not = 42

        defs = WithMixedAttrs.get_event_definitions()
        assert "event_a" in defs
        assert "not_a_pub" not in defs
        assert "also_not" not in defs


class TestMultiPublisherValidPublicationsCache:
    def test_returns_frozenset(self) -> None:
        result = PublisherBase._valid_publications()
        assert isinstance(result, frozenset)

    def test_returns_same_object_on_repeated_calls(self) -> None:
        result1 = PublisherBase._valid_publications()
        result2 = PublisherBase._valid_publications()
        assert result1 is result2

    def test_contains_all_publications(self) -> None:
        valid = PublisherChild._valid_publications()
        assert PublisherChild.event_a in valid
        assert PublisherChild.event_b in valid

    def test_is_publication_valid_uses_frozenset(self) -> None:
        """is_publication_valid should correctly accept defined publications."""
        assert PublisherChild.is_publication_valid(PublisherChild.event_a)
        assert PublisherChild.is_publication_valid(PublisherChild.event_b)

    def test_is_publication_valid_rejects_unknown(self) -> None:
        unknown = EventPublication(Events.C, EventC)
        with pytest.raises(ValueError, match="Invalid publication"):
            PublisherBase.is_publication_valid(unknown)

    def test_is_publication_valid_no_raise(self) -> None:
        unknown = EventPublication(Events.C, EventC)
        assert PublisherBase.is_publication_valid(unknown, raise_error=False) is False

    def test_subclass_frozenset_independent(self) -> None:
        base_valid = PublisherBase._valid_publications()
        child_valid = PublisherChild._valid_publications()
        assert len(base_valid) == 1
        assert len(child_valid) == 2
        assert base_valid is not child_valid


# --- MultiSubscriber caching tests ---


class MockPublisher(EventPublisher):
    def __init__(self) -> None:
        super().__init__(EventPublication(Events.A, EventA))


class SubscriberBase(MultiSubscriber):
    def __init__(self) -> None:
        super().__init__()
        self._logger = logging.getLogger(__name__)

    def logger(self) -> logging.Logger:
        return self._logger

    def handle(self, event: Any) -> None:
        pass

    @staticmethod
    def _adapter(
        handler: Any,
        subscriber: Any,
        arg: Any,
        current_event_tag: int,
        current_event_caller: EventPublisher,
    ) -> None:
        handler(subscriber, arg)

    sub_a = EventSubscription(MockPublisher, Events.A, partial(_adapter, handle))


class SubscriberChild(SubscriberBase):
    def handle_b(self, event: Any) -> None:
        pass

    sub_b = EventSubscription(
        MockPublisher, Events.B, partial(SubscriberBase._adapter, handle_b)
    )


class TestMultiSubscriberGetEventDefinitionsCache:
    def test_returns_correct_definitions(self) -> None:
        defs = SubscriberBase.get_event_definitions()
        assert len(defs) == 1
        assert "sub_a" in defs

    def test_returns_same_object_on_repeated_calls(self) -> None:
        defs1 = SubscriberBase.get_event_definitions()
        defs2 = SubscriberBase.get_event_definitions()
        assert defs1 is defs2

    def test_subclass_gets_own_cache(self) -> None:
        base_defs = SubscriberBase.get_event_definitions()
        child_defs = SubscriberChild.get_event_definitions()
        assert len(base_defs) == 1
        assert len(child_defs) == 2
        assert base_defs is not child_defs

    def test_child_includes_parent_definitions(self) -> None:
        defs = SubscriberChild.get_event_definitions()
        assert "sub_a" in defs
        assert "sub_b" in defs
