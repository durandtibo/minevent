r"""Benchmarks for the registry of the event manager.

Run them explicitly with:

    inv test.benchmark
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from minevent import EventHandler, EventManager

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture


def no_argument() -> None:
    r"""Implement a handler without argument."""


def make_manager(num_events: int, num_handlers: int) -> EventManager:
    r"""Create a manager with ``num_handlers`` handlers on each of
    ``num_events`` events."""
    manager = EventManager()
    for i in range(num_events):
        for _ in range(num_handlers):
            manager.add_event_handler(f"event_{i}", EventHandler(no_argument))
    return manager


def test_add_event_handler_and_remove_benchmark(benchmark: BenchmarkFixture) -> None:
    # Adding alone would grow the registry at each round, so the registration is removed
    manager = EventManager()
    handler = EventHandler(no_argument)

    def add_and_remove() -> bool:
        return manager.add_event_handler("e", handler).remove()

    benchmark(add_and_remove)


@pytest.mark.parametrize("num_handlers", [1, 10, 100])
def test_subscription_remove_last_benchmark(benchmark: BenchmarkFixture, num_handlers: int) -> None:
    manager = make_manager(1, num_handlers)
    handler = EventHandler(no_argument)

    def add_last_and_remove_it() -> bool:
        # remove() searches the list of the event from the start, so removing the last
        # registration costs the most and grows with the number of handlers
        return manager.add_event_handler("event_0", handler).remove()

    benchmark(add_last_and_remove_it)


def test_subscription_remove_many_lifo_benchmark(benchmark: BenchmarkFixture) -> None:
    def add_many_and_remove_in_reverse_order() -> None:
        # The order of nested ``with manager.add_event_handler(...)`` blocks. A list registry
        # scans the whole list for each removal, so the total cost is quadratic.
        manager = EventManager()
        handler = EventHandler(no_argument)
        subscriptions = [manager.add_event_handler("event_0", handler) for _ in range(10_000)]
        for subscription in reversed(subscriptions):
            subscription.remove()

    benchmark.pedantic(add_many_and_remove_in_reverse_order, rounds=3, iterations=1)


def test_event_handler_construct_benchmark(benchmark: BenchmarkFixture) -> None:
    benchmark(EventHandler, no_argument)


def test_event_handler_construct_filter_payload_benchmark(benchmark: BenchmarkFixture) -> None:
    benchmark(EventHandler, no_argument, filter_payload=True)


@pytest.mark.parametrize("num_handlers", [1, 10, 100])
def test_get_subscriptions_benchmark(benchmark: BenchmarkFixture, num_handlers: int) -> None:
    manager = make_manager(1, num_handlers)
    benchmark(manager.get_subscriptions, "event_0")


def test_contains_benchmark(benchmark: BenchmarkFixture) -> None:
    manager = make_manager(100, 1)
    benchmark(manager.__contains__, "event_50")


def test_len_benchmark(benchmark: BenchmarkFixture) -> None:
    manager = make_manager(100, 10)
    benchmark(len, manager)


def test_events_benchmark(benchmark: BenchmarkFixture) -> None:
    manager = make_manager(100, 1)
    benchmark(getattr, manager, "events")


def test_repr_benchmark(benchmark: BenchmarkFixture) -> None:
    manager = make_manager(100, 10)
    benchmark(repr, manager)


def setup_manager_with_handlers() -> tuple[tuple[EventManager], dict[str, object]]:
    r"""Create the arguments of a round: a manager with 100 handlers."""
    return (make_manager(1, 100),), {}


def test_clear_event_benchmark(benchmark: BenchmarkFixture) -> None:
    benchmark.pedantic(
        lambda manager: manager.clear_event("event_0"),
        setup=setup_manager_with_handlers,
        rounds=100,
    )


def test_reset_benchmark(benchmark: BenchmarkFixture) -> None:
    benchmark.pedantic(
        lambda manager: manager.reset(), setup=setup_manager_with_handlers, rounds=100
    )
