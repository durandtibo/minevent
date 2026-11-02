r"""Benchmarks for the dispatch of an event.

Run them explicitly with:

    inv test.benchmark

They only use the public API, so that they run unchanged on any design
of the package.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from minevent import EventHandler, EventManager, PeriodicCondition

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture


def no_argument() -> None:
    r"""Implement a handler without argument."""


def with_payload(epoch: int = 0, loss: float = 0.0) -> None:
    r"""Implement a handler that accepts two payload keys."""


async def async_no_argument() -> None:
    r"""Implement a coroutine handler without argument."""


def make_manager(num_handlers: int) -> EventManager:
    r"""Create a manager with ``num_handlers`` handlers on ``"e"``."""
    manager = EventManager()
    for _ in range(num_handlers):
        manager.add_event_handler("e", EventHandler(no_argument))
    return manager


def test_trigger_event_no_handler_benchmark(benchmark: BenchmarkFixture) -> None:
    manager = EventManager()
    benchmark(manager.trigger_event, "e")


@pytest.mark.parametrize("num_handlers", [1, 10, 100])
def test_trigger_event_handlers_benchmark(benchmark: BenchmarkFixture, num_handlers: int) -> None:
    manager = make_manager(num_handlers)
    benchmark(manager.trigger_event, "e")


def test_trigger_event_payload_benchmark(benchmark: BenchmarkFixture) -> None:
    manager = EventManager()
    manager.add_event_handler("e", EventHandler(with_payload))
    benchmark(manager.trigger_event, "e", epoch=1, loss=0.5)


def test_trigger_event_filter_payload_benchmark(benchmark: BenchmarkFixture) -> None:
    manager = EventManager()
    manager.add_event_handler("e", EventHandler(with_payload, filter_payload=True))
    benchmark(manager.trigger_event, "e", epoch=1, loss=0.5, extra=1)


def test_trigger_event_periodic_condition_benchmark(benchmark: BenchmarkFixture) -> None:
    manager = EventManager()
    manager.add_event_handler("e", EventHandler(no_argument, condition=PeriodicCondition(10)))
    benchmark(manager.trigger_event, "e")


def test_trigger_event_callable_condition_benchmark(benchmark: BenchmarkFixture) -> None:
    manager = EventManager()
    manager.add_event_handler("e", EventHandler(no_argument, condition=lambda: True))
    benchmark(manager.trigger_event, "e")


def test_trigger_event_many_events_benchmark(benchmark: BenchmarkFixture) -> None:
    manager = EventManager()
    for i in range(1000):
        manager.add_event_handler(f"event_{i}", EventHandler(no_argument))
    benchmark(manager.trigger_event, "event_500")


def test_trigger_event_once_benchmark(benchmark: BenchmarkFixture) -> None:
    manager = EventManager()
    handler = EventHandler(no_argument)

    def register_and_trigger() -> None:
        manager.add_event_handler("e", handler, once=True)
        manager.trigger_event("e")

    benchmark(register_and_trigger)


def test_atrigger_event_benchmark(benchmark: BenchmarkFixture) -> None:
    manager = EventManager()
    manager.add_event_handler("e", EventHandler(async_no_argument))

    async def trigger_many() -> None:
        # 100 triggers per round, because asyncio.run alone costs more than a trigger
        for _ in range(100):
            await manager.atrigger_event("e")

    benchmark(lambda: asyncio.run(trigger_many()))
