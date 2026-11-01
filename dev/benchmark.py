r"""Measure the cost of the main operations of ``minevent``.

Run it before and after a change that touches ``EventManager``,
``EventHandler`` or ``Subscription``: a pull request that makes a row
more than 10% slower should explain why.

Usage: ``.venv/bin/python dev/benchmark.py``
"""

from __future__ import annotations

import timeit
from typing import TYPE_CHECKING

from minevent import EventHandler, EventManager, PeriodicCondition

if TYPE_CHECKING:
    from collections.abc import Callable


def no_argument() -> None:
    r"""Implement a handler without argument."""


def with_payload(epoch: int = 0, loss: float = 0.0) -> None:
    r"""Implement a handler that accepts two payload keys."""


def run(label: str, func: Callable[[], object], number: int = 100_000) -> None:
    r"""Print the best time of a call, in nanoseconds.

    Args:
        label: The name of the benchmark.
        func: The function to time.
        number: The number of calls per repeat.
    """
    best = min(timeit.repeat(func, number=number, repeat=5)) / number * 1e9
    print(f"{label:42s}{best:9.0f} ns")  # noqa: T201


def main() -> None:
    r"""Run all the benchmarks."""
    empty = EventManager()
    run("trigger, no handler", lambda: empty.trigger_event("e"))

    one = EventManager()
    one.add_event_handler("e", EventHandler(no_argument))
    run("trigger, 1 handler", lambda: one.trigger_event("e"))

    payload = EventManager()
    payload.add_event_handler("e", EventHandler(with_payload))
    run(
        "trigger, 1 handler, payload of 2 keys",
        lambda: payload.trigger_event("e", epoch=1, loss=0.5),
    )

    filtered = EventManager()
    filtered.add_event_handler("e", EventHandler(with_payload, filter_payload=True))
    run(
        "trigger, filter_payload, payload of 3 keys",
        lambda: filtered.trigger_event("e", epoch=1, loss=0.5, extra=1),
    )

    periodic = EventManager()
    periodic.add_event_handler("e", EventHandler(no_argument, condition=PeriodicCondition(10)))
    run("trigger, 1 handler, periodic condition", lambda: periodic.trigger_event("e"))

    ten = EventManager()
    for _ in range(10):
        ten.add_event_handler("e", EventHandler(no_argument))
    run("trigger, 10 handlers", lambda: ten.trigger_event("e"), number=20_000)

    manager = EventManager()

    def add_and_remove() -> None:
        manager.add_event_handler("e", EventHandler(no_argument)).remove()

    run("add_event_handler + remove", add_and_remove, number=20_000)


if __name__ == "__main__":
    main()
