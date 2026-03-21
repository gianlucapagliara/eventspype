"""
Benchmarks for eventspype publish hot path.

Run with: python benchmarks/bench_publish.py
"""

import timeit
from dataclasses import dataclass
from enum import Enum
from typing import Any

from eventspype.pub.multipublisher import MultiPublisher
from eventspype.pub.publication import EventPublication
from eventspype.pub.publisher import EventPublisher
from eventspype.sub.subscriber import EventSubscriber
from eventspype.sub.tracker import TrackingEventSubscriber


class Events(Enum):
    EVENT_1 = 1


@dataclass
class SampleEvent:
    value: int


class NoOpSubscriber(EventSubscriber):
    def call(self, arg: Any, current_event_tag: int, current_event_caller: Any) -> None:
        pass


class SampleMultiPublisher(MultiPublisher):
    EVENT_1 = EventPublication(Events.EVENT_1, SampleEvent)


def bench_single_publisher(n_subscribers: int, n_publishes: int = 10000) -> float:
    """Benchmark EventPublisher.publish() with n_subscribers."""
    pub = EventPublication(Events.EVENT_1, SampleEvent)
    publisher = EventPublisher(pub)
    subscribers = [NoOpSubscriber() for _ in range(n_subscribers)]
    for s in subscribers:
        publisher.add_subscriber(s)

    event = SampleEvent(value=42)

    def run() -> None:
        for _ in range(n_publishes):
            publisher.publish(event)

    elapsed = timeit.timeit(run, number=1)
    ops_per_sec = n_publishes / elapsed
    return ops_per_sec


def bench_multi_publisher(n_subscribers: int, n_publishes: int = 10000) -> float:
    """Benchmark MultiPublisher.publish() with validation overhead."""
    publisher = SampleMultiPublisher()
    subscribers = [NoOpSubscriber() for _ in range(n_subscribers)]
    for s in subscribers:
        publisher.add_subscriber(SampleMultiPublisher.EVENT_1, s)

    event = SampleEvent(value=42)

    def run() -> None:
        for _ in range(n_publishes):
            publisher.publish(SampleMultiPublisher.EVENT_1, event)

    elapsed = timeit.timeit(run, number=1)
    ops_per_sec = n_publishes / elapsed
    return ops_per_sec


def bench_tracker(n_events: int = 10000) -> float:
    """Benchmark TrackingEventSubscriber.call() throughput."""
    tracker = TrackingEventSubscriber(event_source="bench", max_len=100)

    def run() -> None:
        for i in range(n_events):
            tracker.call(SampleEvent(value=i), 1, None)

    elapsed = timeit.timeit(run, number=1)
    ops_per_sec = n_events / elapsed
    return ops_per_sec


def main() -> None:
    print("eventspype Performance Benchmarks")
    print("=" * 60)

    print("\nEventPublisher.publish() throughput:")
    for n_sub in [1, 10, 100, 1000]:
        ops = bench_single_publisher(n_sub)
        print(f"  {n_sub:>5} subscribers: {ops:>12,.0f} publishes/sec")

    print("\nMultiPublisher.publish() throughput (with validation):")
    for n_sub in [1, 10, 100]:
        ops = bench_multi_publisher(n_sub)
        print(f"  {n_sub:>5} subscribers: {ops:>12,.0f} publishes/sec")

    print("\nTrackingEventSubscriber.call() throughput:")
    ops = bench_tracker()
    print(f"  {ops:>12,.0f} events/sec")

    print()


if __name__ == "__main__":
    main()
