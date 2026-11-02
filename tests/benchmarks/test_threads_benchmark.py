r"""Benchmarks for the manager used from several threads.

Run them explicitly with:

    inv test.benchmark
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from minevent import EventHandler, EventManager
from tests.integration.helpers import run_threads

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture

NUM_THREADS = 4
NUM_TRIGGERS = 200


def no_argument() -> None:
    r"""Implement a handler without argument."""


def test_trigger_event_threads_benchmark(benchmark: BenchmarkFixture) -> None:
    manager = EventManager()
    manager.add_event_handler("e", EventHandler(no_argument))

    def work(_index: int) -> None:
        for _ in range(NUM_TRIGGERS):
            manager.trigger_event("e")

    benchmark(run_threads, work, NUM_THREADS)


def test_add_and_remove_threads_benchmark(benchmark: BenchmarkFixture) -> None:
    manager = EventManager()
    handler = EventHandler(no_argument)

    def work(_index: int) -> None:
        for _ in range(NUM_TRIGGERS):
            manager.add_event_handler("e", handler).remove()

    benchmark(run_threads, work, NUM_THREADS)
