r"""Benchmarks for the event handlers and the conditions.

Run them explicitly with:

    inv test.benchmark
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from minevent import AfterNCondition, EventHandler, OnceCondition, PeriodicCondition

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture


def no_argument() -> None:
    r"""Implement a handler without argument."""


def with_arguments(a: int, b: int, *, c: int = 0, epoch: int = 0) -> None:
    r"""Implement a handler with positional, keyword and payload
    arguments."""


def test_event_handler_handle_benchmark(benchmark: BenchmarkFixture) -> None:
    handler = EventHandler(no_argument)
    benchmark(handler.handle)


def test_event_handler_handle_arguments_benchmark(benchmark: BenchmarkFixture) -> None:
    handler = EventHandler(with_arguments, handler_args=(1, 2), handler_kwargs={"c": 3})
    benchmark(handler.handle, epoch=1)


def test_event_handler_handle_condition_false_benchmark(benchmark: BenchmarkFixture) -> None:
    handler = EventHandler(no_argument, condition=lambda: False)
    benchmark(handler.handle)


def test_event_handler_repr_benchmark(benchmark: BenchmarkFixture) -> None:
    handler = EventHandler(with_arguments, handler_args=(1, 2), handler_kwargs={"c": 3})
    benchmark(repr, handler)


def test_periodic_condition_call_benchmark(benchmark: BenchmarkFixture) -> None:
    benchmark(PeriodicCondition(freq=10))


def test_periodic_condition_skip_first_call_benchmark(benchmark: BenchmarkFixture) -> None:
    benchmark(PeriodicCondition(freq=10, skip_first=True))


def test_after_n_condition_call_benchmark(benchmark: BenchmarkFixture) -> None:
    benchmark(AfterNCondition(5))


def test_once_condition_call_benchmark(benchmark: BenchmarkFixture) -> None:
    benchmark(OnceCondition())
