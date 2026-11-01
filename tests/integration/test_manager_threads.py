from __future__ import annotations

import threading

import pytest

from minevent import EventHandler, EventManager
from tests.integration.helpers import run_threads

NUM_THREADS = 8
NUM_ITERATIONS = 200


def test_add_event_handler_from_threads() -> None:
    """Test that handlers added from several threads are all registered
    and unique."""
    manager = EventManager()
    calls: list[int] = []
    lock = threading.Lock()

    def make_handler(value: int) -> EventHandler:
        def handler() -> None:
            with lock:
                calls.append(value)

        return EventHandler(handler)

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

    manager.add_event_handler("my_event", EventHandler(handler, handler_args=(0,)))

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
                manager.add_event_handler("my_event", EventHandler(len, handler_args=([],)))
            else:
                manager.trigger_event("my_event")

    run_threads(work, NUM_THREADS)
    manager.trigger_event("my_event")
    assert manager.has_event_handler(EventHandler(len, handler_args=([],)), "my_event")


def test_subscription_remove_from_threads() -> None:
    """Test that each registration is removed exactly once when
    several threads remove them."""
    manager = EventManager()
    subscriptions = [
        manager.add_event_handler("my_event", EventHandler(len, handler_args=([],)))
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

    manager.add_event_handler("my_event", EventHandler(handler), once=True)

    def work(_index: int) -> None:
        manager.trigger_event("my_event")

    run_threads(work, NUM_THREADS)
    assert len(calls) == 1


def test_run_threads_propagates_exception() -> None:
    """Test that the helper reports the exception of a thread."""

    def work(_index: int) -> None:
        msg = "boom"
        raise ValueError(msg)

    with pytest.raises(RuntimeError, match=r"raised an exception: ValueError\('boom'\)"):
        run_threads(work, 2)
