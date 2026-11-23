r"""Benchmarks for the options of a registration and the conditions.

Run them explicitly with:

    inv test.benchmark
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

from minevent import AfterNCondition, EventManager, PeriodicCondition

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture


def no_argument() -> None:
    r"""Implement a handler without argument."""


def with_arguments(a: int, b: int, *, c: int = 0, epoch: int = 0) -> None:
    r"""Implement a handler with positional, keyword and payload
    arguments."""


def test_add_event_handler_partial_benchmark(benchmark: BenchmarkFixture) -> None:
    manager = EventManager()
    handler = functools.partial(with_arguments, 1, 2, c=3)

    def add_and_remove() -> None:
        manager.add_event_handler("e", handler).remove()

    benchmark(add_and_remove)


def test_add_event_handler_options_benchmark(benchmark: BenchmarkFixture) -> None:
    manager = EventManager()

    def add_and_remove() -> None:
        manager.add_event_handler(
            "e", no_argument, once=True, condition=lambda: True, filter_payload=True
        ).remove()

    benchmark(add_and_remove)


def test_periodic_condition_call_benchmark(benchmark: BenchmarkFixture) -> None:
    benchmark(PeriodicCondition(freq=10))


def test_periodic_condition_skip_first_call_benchmark(benchmark: BenchmarkFixture) -> None:
    benchmark(PeriodicCondition(freq=10, skip_first=True))


def test_after_n_condition_call_benchmark(benchmark: BenchmarkFixture) -> None:
    benchmark(AfterNCondition(5))
