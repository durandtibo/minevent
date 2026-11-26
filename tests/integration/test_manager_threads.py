from __future__ import annotations

import functools
import threading
from typing import TYPE_CHECKING

import pytest

from minevent import Context, EventManager, PeriodicCondition
from tests.integration.helpers import run_threads

if TYPE_CHECKING:
    from collections.abc import Callable

NUM_THREADS = 8
NUM_ITERATIONS = 200


def test_add_event_handler_from_threads() -> None:
    """Test that handlers added from several threads are all registered
    and unique."""
    manager = EventManager()
    calls: list[int] = []
    lock = threading.Lock()

    def make_handler(value: int) -> Callable[[], None]:
        def handler() -> None:
            with lock:
                calls.append(value)

        return handler

    def work(index: int) -> None:
        for i in range(NUM_ITERATIONS):
            manager.add_event_handler("my_event", make_handler(index * NUM_ITERATIONS + i))

    run_threads(work, NUM_THREADS)
    manager.trigger_event("my_event")
    assert len(calls) == NUM_THREADS * NUM_ITERATIONS
    assert len(set(calls)) == NUM_THREADS * NUM_ITERATIONS


def test_trigger_event_from_threads() -> None:
    """Test that every thread runs the registered handler for each
    trigger."""
    manager = EventManager()
    calls: list[int] = []
    lock = threading.Lock()

    def handler(index: int) -> None:
        with lock:
            calls.append(index)

    manager.add_event_handler("my_event", functools.partial(handler, 0))

    def work(_index: int) -> None:
        for _ in range(NUM_ITERATIONS):
            manager.trigger_event("my_event")

    run_threads(work, NUM_THREADS)
    assert len(calls) == NUM_THREADS * NUM_ITERATIONS


def test_add_and_trigger_from_threads() -> None:
    """Test that triggering while other threads add handlers neither
    fails nor loses a handler."""
    manager = EventManager()

    def work(index: int) -> None:
        for _ in range(NUM_ITERATIONS):
            if index % 2:
                manager.add_event_handler("my_event", functools.partial(len, []))
            else:
                manager.trigger_event("my_event")

    run_threads(work, NUM_THREADS)
    manager.trigger_event("my_event")
    assert len(manager.get_subscriptions("my_event")) == NUM_ITERATIONS * (NUM_THREADS // 2)


def test_subscription_remove_from_threads() -> None:
    """Test that each registration is removed exactly once when several
    threads remove them."""
    manager = EventManager()
    subscriptions = [
        manager.add_event_handler("my_event", functools.partial(len, []))
        for _ in range(NUM_THREADS * NUM_ITERATIONS)
    ]
    removed: list[bool] = []
    lock = threading.Lock()

    def work(_index: int) -> None:
        for subscription in subscriptions:
            result = subscription.remove()
            with lock:
                removed.append(result)

    run_threads(work, NUM_THREADS)
    assert removed.count(True) == NUM_THREADS * NUM_ITERATIONS
    assert manager.events == []


def test_once_handler_runs_once_from_threads() -> None:
    """Test that a handler registered with ``once`` runs exactly once
    even if several threads trigger the event."""
    manager = EventManager()
    calls: list[int] = []
    lock = threading.Lock()

    def handler() -> None:
        with lock:
            calls.append(1)

    manager.add_event_handler("my_event", handler, once=True)

    def work(_index: int) -> None:
        manager.trigger_event("my_event")

    run_threads(work, NUM_THREADS)
    assert len(calls) == 1


def test_once_with_condition_runs_at_most_once_from_threads() -> None:
    """Test that a ``once`` handler with a true condition runs exactly
    once even if several threads trigger the event."""
    manager = EventManager()
    calls: list[int] = []
    lock = threading.Lock()

    def handler() -> None:
        with lock:
            calls.append(1)

    manager.add_event_handler("my_event", handler, once=True, condition=lambda: True)

    def work(_index: int) -> None:
        manager.trigger_event("my_event")

    run_threads(work, NUM_THREADS)
    assert len(calls) == 1


def test_once_handler_runs_once_when_snapshots_taken_before_dispatch() -> None:
    """Test that a ``once`` handler runs once even if every thread took
    its snapshot before any thread dispatched."""
    manager = EventManager()
    calls: list[int] = []
    lock = threading.Lock()
    barrier = threading.Barrier(NUM_THREADS)

    def handler() -> None:
        with lock:
            calls.append(1)

    manager.add_event_handler("my_event", handler, once=True)

    def work(_index: int) -> None:
        subscriptions = manager.get_subscriptions("my_event")
        barrier.wait()
        for subscription in subscriptions:
            if not subscription.once or subscription.remove():
                handler()

    run_threads(work, NUM_THREADS)
    assert len(calls) == 1


def test_run_threads_propagates_exception() -> None:
    """Test that the helper reports the exception of a thread."""

    def work(_index: int) -> None:
        msg = "boom"
        raise ValueError(msg)

    with pytest.raises(RuntimeError, match=r"raised an exception: ValueError\('boom'\)"):
        run_threads(work, 2)


def test_remove_from_threads_registrations_added_by_other_threads() -> None:
    """Test that the registrations added by some threads can be removed
    by other threads, each exactly once."""
    manager = EventManager()
    subscriptions = [
        manager.add_event_handler("my_event", lambda: None)
        for _ in range(NUM_THREADS * NUM_ITERATIONS)
    ]
    results: list[bool] = []
    lock = threading.Lock()

    def work(index: int) -> None:
        for subscription in subscriptions[index::NUM_THREADS]:
            removed = subscription.remove()
            with lock:
                results.append(removed)

    run_threads(work, NUM_THREADS)
    assert results.count(True) == len(subscriptions)
    assert manager.events == []


def test_add_event_handler_options_from_threads() -> None:
    """Test that registrations with a stateful condition and a partial,
    added from several threads, all run with the right arguments."""
    manager = EventManager()
    calls: list[tuple[int, object]] = []
    lock = threading.Lock()

    def record(index: int, context: Context) -> None:
        with lock:
            calls.append((index, context["epoch"]))

    def work(index: int) -> None:
        manager.add_event_handler(
            "my_event",
            functools.partial(record, index),
            condition=PeriodicCondition(freq=1),
        )
        manager.add_event_handler(
            "my_event",
            functools.partial(record, index),
            once=True,
            condition=PeriodicCondition(freq=1, start=0),
        )

    run_threads(work, NUM_THREADS)
    manager.trigger_event("my_event", {"epoch": 3, "loss": 0.5})
    assert sorted(calls) == sorted([(i, 3) for i in range(NUM_THREADS)] * 2)
    assert len(manager.get_subscriptions("my_event")) == NUM_THREADS


def test_remove_from_threads_while_triggering() -> None:
    """Test that a ``once`` handler runs at most once when its
    registration is removed in another thread, and never runs after the
    removal is complete."""
    manager = EventManager()
    calls: list[int] = []
    lock = threading.Lock()

    def make_handler(value: int) -> Callable[[], None]:
        def handler() -> None:
            with lock:
                calls.append(value)

        return handler

    subscriptions = [
        manager.add_event_handler("my_event", make_handler(i), once=True)
        for i in range(NUM_ITERATIONS)
    ]

    def work(index: int) -> None:
        if index % 2 == 0:
            manager.trigger_event("my_event")
        else:
            for subscription in subscriptions:
                subscription.remove()

    run_threads(work, NUM_THREADS)
    n_calls = len(calls)
    manager.trigger_event("my_event")
    assert len(calls) == n_calls
    assert len(set(calls)) == len(calls)
    assert manager.events == []


class LockingFinalizer:
    r"""Implement a handler whose finalizer waits for another thread that
    uses the manager.

    Args:
        manager: The manager used by the other thread.
        finished: The list that receives ``True`` if the thread finished
            while the finalizer was waiting, ``False`` otherwise.
    """

    def __init__(self, manager: EventManager, finished: list[bool]) -> None:
        self._manager = manager
        self._finished = finished

    def __del__(self) -> None:
        thread = threading.Thread(target=repr, args=(self._manager,), daemon=True)
        thread.start()
        thread.join(timeout=1.0)
        self._finished.append(not thread.is_alive())

    def __call__(self) -> None:
        r"""Implement a handler."""


def test_clear_event_releases_handlers_without_lock() -> None:
    """Test that ``clear_event`` releases the handlers without the lock,
    so a finalizer can wait for a thread that uses the manager."""
    manager = EventManager()
    finished: list[bool] = []
    manager.add_event_handler("my_event", LockingFinalizer(manager, finished))
    manager.add_event_handler("my_event", LockingFinalizer(manager, finished))
    manager.clear_event("my_event")
    assert finished == [True, True]


def test_reset_releases_handlers_without_lock() -> None:
    """Test that ``reset`` releases the handlers of every event without
    the lock, so a finalizer can wait for a thread that uses the
    manager."""
    manager = EventManager()
    finished: list[bool] = []
    manager.add_event_handler("my_event", LockingFinalizer(manager, finished))
    manager.add_event_handler("my_other_event", LockingFinalizer(manager, finished))
    manager.reset()
    assert finished == [True, True]
