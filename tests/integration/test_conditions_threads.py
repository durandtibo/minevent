from __future__ import annotations

import copy
import multiprocessing
import threading
from concurrent.futures import ProcessPoolExecutor
from typing import TYPE_CHECKING

from minevent import Context, EventManager, PeriodicCondition
from tests.integration.helpers import run_threads

if TYPE_CHECKING:
    from collections.abc import Callable

NUM_THREADS = 8
NUM_ITERATIONS = 20_000


def count_true_calls(condition: Callable[[Context], bool]) -> int:
    r"""Call a condition from several threads.

    Args:
        condition: The condition to call ``NUM_ITERATIONS`` times in
            each of the ``NUM_THREADS`` threads.

    Returns:
        The number of calls that returned ``True``.
    """
    counts: list[int] = []
    lock = threading.Lock()

    def work(_index: int) -> None:
        context = Context()
        count = sum(condition(context) for _ in range(NUM_ITERATIONS))
        with lock:
            counts.append(count)

    run_threads(work, NUM_THREADS)
    return sum(counts)


def test_periodic_condition_counts_every_call_from_threads() -> None:
    """Test that a ``PeriodicCondition`` called from several threads is
    true for exactly one call in ``freq``."""
    assert count_true_calls(PeriodicCondition(freq=2)) == 80_000


def test_periodic_condition_with_start_counts_every_call_from_threads() -> None:
    """Test that a ``PeriodicCondition`` with a ``start``, called from
    several threads, is true for exactly one call in ``freq`` after
    ``start``."""
    assert count_true_calls(PeriodicCondition(freq=2, start=100_000)) == 30_000


def test_periodic_condition_warm_up_counts_every_call_from_threads() -> None:
    """Test that a ``PeriodicCondition`` with a ``freq`` of 1, called
    from several threads, is false for exactly ``start`` calls."""
    assert count_true_calls(PeriodicCondition(freq=1, start=100_000)) == 60_000


def test_periodic_condition_step_is_exact_after_calls_from_threads() -> None:
    """Test that the counter of a ``PeriodicCondition`` has the exact
    number of calls made from several threads."""
    condition = PeriodicCondition(freq=2)
    count_true_calls(condition)
    assert repr(condition) == "PeriodicCondition(freq=2, start=0, step=160000)"


def test_condition_of_a_trigger_counts_every_trigger_from_threads() -> None:
    """Test that the condition of a registration counts every trigger of
    several threads."""
    manager = EventManager()
    calls: list[int] = []
    lock = threading.Lock()

    def handler(_: Context) -> None:
        with lock:
            calls.append(1)

    manager.add_event_handler("my_event", handler, condition=PeriodicCondition(freq=4))

    def work(_index: int) -> None:
        for _ in range(1_000):
            manager.trigger_event("my_event")

    run_threads(work, NUM_THREADS)
    assert len(calls) == 2_000


def test_periodic_condition_goes_to_a_worker_process() -> None:
    """Test that a condition sent to a worker process comes back with
    the same state."""
    condition = PeriodicCondition(freq=2)
    condition(Context())
    spawn = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=1, mp_context=spawn) as executor:
        result = executor.submit(copy.copy, condition).result()
    assert repr(result) == "PeriodicCondition(freq=2, start=0, step=1)"
