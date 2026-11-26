r"""Benchmarks for the options of a registration and the conditions.

Run them explicitly with:

    inv test.benchmark
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

from minevent import Context, EventManager, PeriodicCondition

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture


def ignore_context(_: Context) -> None:
    r"""Implement a handler that ignores the context."""


def with_arguments(a: int, b: int, context: Context, *, c: int = 0) -> None:
    r"""Implement a handler with bound arguments and the context."""


def test_add_event_handler_partial_benchmark(benchmark: BenchmarkFixture) -> None:
    manager = EventManager()
    handler = functools.partial(with_arguments, 1, 2, c=3)

    def add_and_remove() -> None:
        manager.add_event_handler("e", handler).remove()

    benchmark(add_and_remove)


def test_add_event_handler_options_benchmark(benchmark: BenchmarkFixture) -> None:
    manager = EventManager()

    def add_and_remove() -> None:
        manager.add_event_handler("e", ignore_context, once=True, condition=lambda _: True).remove()

    benchmark(add_and_remove)


def test_periodic_condition_call_benchmark(benchmark: BenchmarkFixture) -> None:
    benchmark(PeriodicCondition(freq=10), Context())


def test_periodic_condition_start_call_benchmark(benchmark: BenchmarkFixture) -> None:
    benchmark(PeriodicCondition(freq=10, start=10), Context())
