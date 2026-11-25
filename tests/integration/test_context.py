from __future__ import annotations

import asyncio
import copy
import dataclasses
import multiprocessing
import threading
from concurrent.futures import ProcessPoolExecutor
from typing import Any

import pytest

from minevent import Context, EventManager
from tests.integration.helpers import run_threads

NUM_THREADS = 8
NUM_ITERATIONS = 50


def test_handlers_read_different_keys() -> None:
    """Test that handlers of one event read different keys of the same
    trigger, and that a handler without parameter still runs."""
    manager = EventManager()
    calls: list[tuple[str, object]] = []
    manager.add_event_handler(
        "epoch_end", lambda context: calls.append(("epoch", context["epoch"]))
    )
    manager.add_event_handler("epoch_end", lambda context: calls.append(("loss", context["loss"])))
    manager.add_event_handler("epoch_end", lambda: calls.append(("none", None)))
    manager.trigger_event("epoch_end", {"epoch": 3, "loss": 0.5, "lr": 0.1})
    assert calls == [("epoch", 3), ("loss", 0.5), ("none", None)]


def test_extra_keys_do_not_break_handlers() -> None:
    """Test that a key that no handler reads is ignored."""
    manager = EventManager()
    calls: list[object] = []
    manager.add_event_handler("epoch_end", lambda context: calls.append(context["epoch"]))
    manager.trigger_event("epoch_end", {"epoch": 3, "unused": 1, "other": "a"})
    assert calls == [3]


def test_missing_key_with_get_uses_the_default() -> None:
    """Test that a handler that reads a missing key with ``get`` gets
    its default."""
    manager = EventManager()
    calls: list[object] = []
    manager.add_event_handler("epoch_end", lambda context: calls.append(context.get("lr", 0.1)))
    manager.trigger_event("epoch_end", {"epoch": 3})
    assert calls == [0.1]


class ReprRaises(str):
    r"""Implement a key whose ``repr`` raises."""

    __slots__ = ()

    def __repr__(self) -> str:
        msg = "the keys were formatted"
        raise AssertionError(msg)


def test_handler_reads_a_missing_key_without_formatting_the_keys() -> None:
    """Test that a handler that reads a missing key with ``get`` and
    ``in`` never runs the ``repr`` of the keys of the context."""
    manager = EventManager()
    results: list[tuple[object, bool]] = []
    manager.add_event_handler(
        "epoch_end", lambda context: results.append((context.get("lr", 0.1), "lr" in context))
    )
    manager.trigger_event("epoch_end", {ReprRaises("epoch"): 3})
    assert results == [(0.1, False)]


def test_missing_key_with_getitem_raises_key_error_and_skips_next_handlers() -> None:
    """Test that a handler that reads a missing key with ``[]`` raises a
    ``KeyError`` that lists the available keys, and that the next
    handlers are skipped."""
    manager = EventManager()
    calls: list[str] = []
    manager.add_event_handler("epoch_end", lambda context: calls.append(str(context["lr"])))
    manager.add_event_handler("epoch_end", lambda: calls.append("next"))
    with pytest.raises(KeyError, match=r"key 'lr' not found.*\['epoch'\]"):
        manager.trigger_event("epoch_end", {"epoch": 3})
    assert calls == []


def test_missing_key_with_getitem_adds_a_note_that_names_the_handler() -> None:
    """Test that the ``KeyError`` of a missing key has a note with the
    event and the handler."""
    manager = EventManager()

    def read_lr(context: Context) -> None:
        context["lr"]

    manager.add_event_handler("epoch_end", read_lr)
    with pytest.raises(KeyError, match=r"key 'lr' not found") as exc_info:
        manager.trigger_event("epoch_end", {"epoch": 3})
    assert exc_info.value.__notes__[0].endswith("read_lr while handling the event 'epoch_end'")


@dataclasses.dataclass(frozen=True)
class FrozenError(Exception):
    r"""Implement an exception that forbids new attributes."""

    key: str


def test_frozen_exception_of_a_handler_reaches_the_caller() -> None:
    """Test that a frozen dataclass exception raised by a handler
    reaches the caller of ``atrigger_event`` unchanged."""
    manager = EventManager()
    error = FrozenError("lr")

    async def handler() -> None:
        await asyncio.sleep(0)
        raise error

    manager.add_event_handler("epoch_end", handler)
    with pytest.raises(FrozenError, match=r"lr") as exc_info:
        asyncio.run(manager.atrigger_event("epoch_end"))
    assert exc_info.value is error


def test_missing_key_in_a_condition_adds_a_note_that_names_the_condition() -> None:
    """Test that the ``KeyError`` of a missing key in a condition has a
    note with the event, the condition and the handler."""
    manager = EventManager()

    def is_late(context: Context) -> bool:
        return context["epoch"] > 2

    def log_epoch() -> None:
        pass

    manager.add_event_handler("epoch_end", log_epoch, condition=is_late)
    with pytest.raises(KeyError, match=r"key 'epoch' not found") as exc_info:
        manager.trigger_event("epoch_end")
    assert exc_info.value.__notes__ == [
        (
            f"raised by the condition {is_late.__qualname__} of {log_epoch.__qualname__} "
            "while handling the event 'epoch_end'"
        )
    ]


def test_context_is_read_only_for_a_handler() -> None:
    """Test that a handler cannot change the context seen by the next
    handler."""
    manager = EventManager()
    seen: list[object] = []

    def mutate(context: Any) -> None:
        with pytest.raises(TypeError, match=r"does not support item assignment"):
            context["epoch"] = 0

    manager.add_event_handler("epoch_end", mutate)
    manager.add_event_handler("epoch_end", lambda context: seen.append(context["epoch"]))
    manager.trigger_event("epoch_end", {"epoch": 3})
    assert seen == [3]


def test_builtin_bound_method_receives_the_context() -> None:
    """Test that a built-in bound method with one parameter is called
    with the context."""
    manager = EventManager()
    contexts: list[Context] = []
    manager.add_event_handler("epoch_end", contexts.append)
    manager.trigger_event("epoch_end", {"epoch": 3})
    assert contexts == [{"epoch": 3}]


def test_builtin_bound_method_without_parameter_is_called_without_argument() -> None:
    """Test that a built-in bound method without parameter is called
    without argument."""
    manager = EventManager()
    values = [1, 2]
    manager.add_event_handler("epoch_end", values.clear)
    manager.trigger_event("epoch_end", {"epoch": 3})
    assert values == []


def test_atrigger_event_passes_the_context_to_sync_and_async_handlers() -> None:
    """Test that ``atrigger_event`` passes the same context to
    synchronous and coroutine handlers, and calls a handler without
    parameter without argument."""
    manager = EventManager()
    calls: list[tuple[str, object]] = []

    async def read_epoch(context: Context) -> None:
        await asyncio.sleep(0)
        calls.append(("async", context["epoch"]))

    manager.add_event_handler("epoch_end", lambda context: calls.append(("sync", context["loss"])))
    manager.add_event_handler("epoch_end", read_epoch)
    manager.add_event_handler("epoch_end", lambda: calls.append(("none", None)))
    asyncio.run(manager.atrigger_event("epoch_end", {"epoch": 3, "loss": 0.5}))
    assert calls == [("sync", 0.5), ("async", 3), ("none", None)]


def test_atrigger_event_missing_key_raises_key_error() -> None:
    """Test that a coroutine handler that reads a missing key with
    ``[]`` raises a ``KeyError`` that has the note of the handler."""
    manager = EventManager()

    async def read_lr(context: Context) -> None:
        await asyncio.sleep(0)
        context["lr"]

    manager.add_event_handler("epoch_end", read_lr)
    with pytest.raises(KeyError, match=r"key 'lr' not found") as exc_info:
        asyncio.run(manager.atrigger_event("epoch_end", {"epoch": 3}))
    assert exc_info.value.__notes__[0].endswith("read_lr while handling the event 'epoch_end'")


def test_trigger_event_from_threads_gives_each_trigger_its_own_context() -> None:
    """Test that triggers from several threads give each handler the
    context of its own trigger, and never the payload of another
    thread."""
    manager = EventManager()
    calls: list[tuple[object, object]] = []
    lock = threading.Lock()

    def record(context: Context) -> None:
        with lock:
            calls.append((context["thread"], context["iteration"]))

    manager.add_event_handler("my_event", record)
    manager.add_event_handler("my_event", record)

    def work(index: int) -> None:
        for iteration in range(NUM_ITERATIONS):
            manager.trigger_event("my_event", {"thread": index, "iteration": iteration})

    run_threads(work, NUM_THREADS)
    expected = [(i, j) for i in range(NUM_THREADS) for j in range(NUM_ITERATIONS)] * 2
    assert sorted(calls) == sorted(expected)


def test_handlers_read_different_keys_from_threads() -> None:
    """Test that handlers that read different keys, and one that reads a
    missing key with ``get``, run once per trigger from several
    threads."""
    manager = EventManager()
    calls: list[tuple[str, object]] = []
    lock = threading.Lock()

    def append(name: str, value: object) -> None:
        with lock:
            calls.append((name, value))

    manager.add_event_handler("my_event", lambda context: append("a", context["a"]))
    manager.add_event_handler("my_event", lambda context: append("b", context["b"]))
    manager.add_event_handler("my_event", lambda context: append("c", context.get("c", -1)))

    def work(index: int) -> None:
        manager.trigger_event("my_event", {"a": index, "b": index * 2})

    run_threads(work, NUM_THREADS)
    expected = [
        (name, value)
        for i in range(NUM_THREADS)
        for name, value in (("a", i), ("b", i * 2), ("c", -1))
    ]
    assert sorted(calls) == sorted(expected)


def test_atrigger_event_from_threads() -> None:
    """Test that ``atrigger_event`` run in several threads gives each
    handler the context of its own trigger."""
    manager = EventManager()
    calls: list[int] = []
    lock = threading.Lock()

    async def record(context: Context) -> None:
        await asyncio.sleep(0)
        with lock:
            calls.append(int(str(context["thread"])))

    manager.add_event_handler("my_event", record)

    def work(index: int) -> None:
        asyncio.run(manager.atrigger_event("my_event", {"thread": index}))

    run_threads(work, NUM_THREADS)
    assert sorted(calls) == list(range(NUM_THREADS))


def test_condition_reads_the_payload() -> None:
    """Test that a condition with a parameter decides from the payload
    of each trigger, and that a condition without parameter still
    works."""
    manager = EventManager()
    calls: list[str] = []
    manager.add_event_handler(
        "epoch_end",
        lambda context: calls.append(f"late {context['epoch']}"),
        condition=lambda context: context.get("epoch", 0) >= 2,
    )
    manager.add_event_handler("epoch_end", lambda: calls.append("always"), condition=lambda: True)
    for epoch in range(3):
        manager.trigger_event("epoch_end", {"epoch": epoch})
    assert calls == ["always", "always", "late 2", "always"]


def test_once_waits_for_a_condition_that_reads_the_payload() -> None:
    """Test that a ``once`` registration runs the first time its
    condition is ``True`` for the payload, and only once."""
    manager = EventManager()
    calls: list[object] = []
    manager.add_event_handler(
        "epoch_end",
        lambda context: calls.append(context["epoch"]),
        once=True,
        condition=lambda context: context["epoch"] >= 2,
    )
    for epoch in range(5):
        manager.trigger_event("epoch_end", {"epoch": epoch})
    assert calls == [2]


def test_condition_reads_the_payload_with_atrigger_event() -> None:
    """Test that ``atrigger_event`` passes the context to a
    condition."""
    manager = EventManager()
    calls: list[str] = []
    manager.add_event_handler(
        "epoch_end", lambda: calls.append("run"), condition=lambda context: context["go"]
    )
    asyncio.run(manager.atrigger_event("epoch_end", {"go": False}))
    asyncio.run(manager.atrigger_event("epoch_end", {"go": True}))
    assert calls == ["run"]


def test_condition_reads_the_payload_from_threads() -> None:
    """Test that triggers from several threads evaluate the condition on
    the payload of their own trigger."""
    manager = EventManager()
    calls: list[int] = []
    lock = threading.Lock()

    def record() -> None:
        with lock:
            calls.append(1)

    manager.add_event_handler("my_event", record, condition=lambda context: context["even"])

    def work(index: int) -> None:
        for _ in range(NUM_ITERATIONS):
            manager.trigger_event("my_event", {"even": index % 2 == 0})

    run_threads(work, NUM_THREADS)
    assert len(calls) == NUM_THREADS // 2 * NUM_ITERATIONS


def test_handler_snapshots_the_payload_with_deepcopy() -> None:
    """Test that a handler keeps a deep copy of the context, which a
    later handler that mutates a value does not change."""
    manager = EventManager()
    snapshots: list[Context] = []
    manager.add_event_handler("epoch_end", lambda context: snapshots.append(copy.deepcopy(context)))
    manager.add_event_handler("epoch_end", lambda context: context["losses"].append(0.1))
    manager.trigger_event("epoch_end", {"losses": [0.5]})
    assert snapshots == [{"losses": [0.5]}]


def test_handler_sends_the_context_to_a_worker_process() -> None:
    """Test that the context of a trigger is sent to a worker process
    and comes back as an equal context."""
    manager = EventManager()
    results: list[object] = []
    spawn = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=1, mp_context=spawn) as executor:
        manager.add_event_handler(
            "epoch_end",
            lambda context: results.append(executor.submit(copy.copy, context).result()),
        )
        manager.trigger_event("epoch_end", {"epoch": 3, "losses": [0.5]})
    assert results == [Context({"epoch": 3, "losses": [0.5]})]
