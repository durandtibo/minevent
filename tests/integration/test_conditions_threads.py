from __future__ import annotations

import copy
import multiprocessing
import threading
from concurrent.futures import ProcessPoolExecutor
from typing import TYPE_CHECKING

import pytest

from minevent import AfterNCondition, EventManager, PeriodicCondition
from tests.integration.helpers import run_threads

if TYPE_CHECKING:
    from collections.abc import Callable

NUM_THREADS = 8
NUM_ITERATIONS = 20_000


def count_true_calls(condition: Callable[[], bool]) -> int:
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
        count = sum(condition() for _ in range(NUM_ITERATIONS))
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


def test_after_n_condition_counts_every_call_from_threads() -> None:
    """Test that an ``AfterNCondition`` called from several threads is
    false for exactly ``n`` calls."""
    assert count_true_calls(AfterNCondition(n=100_000)) == 60_000


@pytest.mark.parametrize(
    ("condition_class", "expected"),
    [
        (PeriodicCondition, "PeriodicCondition(freq=2, start=0, step=160,000)"),
        (AfterNCondition, "AfterNCondition(n=2, step=160,000)"),
    ],
)
def test_condition_step_is_exact_after_calls_from_threads(
    condition_class: type[PeriodicCondition | AfterNCondition], expected: str
) -> None:
    """Test that the counter of a built-in condition has the exact
    number of calls made from several threads."""
    condition = condition_class(2)
    count_true_calls(condition)
    assert repr(condition) == expected


def test_condition_of_a_trigger_counts_every_trigger_from_threads() -> None:
    """Test that the condition of a registration counts every trigger of
    several threads."""
    manager = EventManager()
    calls: list[int] = []
    lock = threading.Lock()

    def handler() -> None:
        with lock:
            calls.append(1)

    manager.add_event_handler("my_event", handler, condition=PeriodicCondition(freq=4))

    def work(_index: int) -> None:
        for _ in range(1_000):
            manager.trigger_event("my_event")

    run_threads(work, NUM_THREADS)
    assert len(calls) == 2_000


@pytest.mark.parametrize(
    ("condition_class", "expected"),
    [
        (PeriodicCondition, "PeriodicCondition(freq=2, start=0, step=1)"),
        (AfterNCondition, "AfterNCondition(n=2, step=1)"),
    ],
)
def test_condition_goes_to_a_worker_process(
    condition_class: type[PeriodicCondition | AfterNCondition], expected: str
) -> None:
    """Test that a condition sent to a worker process comes back with
    the same state."""
    condition = condition_class(2)
    condition()
    spawn = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=1, mp_context=spawn) as executor:
        result = executor.submit(copy.copy, condition).result()
    assert repr(result) == expected
