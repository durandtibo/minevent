from __future__ import annotations

import functools
import logging
from typing import Any

import pytest

from minevent import (
    Context,
    EventManager,
)
from tests.unit.utils import trace

logger = logging.getLogger(__name__)

EVENTS = ("my_event", "my_other_event")


async def async_fail() -> None:
    r"""Implements a coroutine handler that raises a
    ``RuntimeError``."""
    msg = "async failed"
    raise RuntimeError(msg)


async def append_async(values: list[str], value: str) -> None:
    r"""Implements a coroutine handler that appends a value."""
    values.append(value)


async def failing_async_handler() -> None:
    msg = "boom"
    raise ValueError(msg)


@trace
def hello_handler() -> None:
    r"""Implements a simple handler that prints hello."""
    logger.info("Hello!")


####################################
#     Tests for atrigger_event     #
####################################


@trace
async def async_handler(context: Context) -> None:
    r"""Implements a coroutine handler that receives the context."""
    logger.info("Async payload: %s", context)


async def test_event_manager_atrigger_event_awaits_coroutine_handler() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", async_handler)
    await manager.atrigger_event("my_event")
    assert async_handler.call_count == 1


async def test_event_manager_atrigger_event_payload() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", async_handler)
    await manager.atrigger_event("my_event", {"epoch": 3})
    assert async_handler.args == ({"epoch": 3},)


async def test_event_manager_atrigger_event_mixes_sync_and_async_in_order() -> None:
    order: list[str] = []
    manager = EventManager()
    manager.add_event_handler("my_event", functools.partial(append_async, order, "first"))
    manager.add_event_handler("my_event", functools.partial(order.append, "second"))
    manager.add_event_handler("my_event", functools.partial(append_async, order, "third"))
    await manager.atrigger_event("my_event")
    assert order == ["first", "second", "third"]


async def test_event_manager_atrigger_event_without_event_handler() -> None:
    await EventManager().atrigger_event("my_event")


async def test_event_manager_atrigger_event_fail_fast() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", async_fail)
    with pytest.raises(RuntimeError, match=r"async failed"):
        await manager.atrigger_event("my_event")


async def test_event_manager_atrigger_event_fail_fast_skips_next_handlers() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", async_fail)
    manager.add_event_handler("my_event", hello_handler)
    with pytest.raises(RuntimeError, match=r"async failed"):
        await manager.atrigger_event("my_event")
    assert hello_handler.call_count == 0


async def test_event_manager_atrigger_event_incorrect_event() -> None:
    bad: Any = 1
    with pytest.raises(TypeError, match=r"event must be a str"):
        await EventManager().atrigger_event(bad)


async def test_event_manager_atrigger_event_once() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", async_handler, once=True)
    await manager.atrigger_event("my_event")
    await manager.atrigger_event("my_event")
    assert async_handler.call_count == 1


async def test_event_manager_atrigger_event_snapshot() -> None:
    manager = EventManager()

    async def add_handler() -> None:
        manager.add_event_handler("my_event", async_handler)

    manager.add_event_handler("my_event", add_handler)
    await manager.atrigger_event("my_event")
    assert async_handler.call_count == 0


############################################################
#     Tests for trigger_event with a coroutine handler     #
############################################################


def test_event_manager_trigger_event_coroutine_handler_raises() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", async_handler)
    with pytest.raises(TypeError, match=r"returned an awaitable; use atrigger_event"):
        manager.trigger_event("my_event")


async def test_event_manager_atrigger_event_handler_raises_adds_note() -> None:
    manager = EventManager()
    handler = failing_async_handler
    manager.add_event_handler("my_event", handler)
    with pytest.raises(ValueError, match=r"boom") as exc_info:
        await manager.atrigger_event("my_event")
    assert exc_info.value.__notes__ == [
        "raised by failing_async_handler while handling the event 'my_event'"
    ]


async def test_event_manager_atrigger_event_on_reads_context() -> None:
    manager = EventManager()
    epochs: list[object] = []

    @manager.on("my_event")
    async def log_epoch(context: Context) -> None:
        epochs.append(context["epoch"])

    await manager.atrigger_event("my_event", {"epoch": 3, "loss": 0.5})
    assert epochs == [3]


async def test_event_manager_atrigger_event_on_condition_false() -> None:
    manager = EventManager()
    manager.on("my_event", condition=lambda: False)(async_handler)
    await manager.atrigger_event("my_event")
    assert async_handler.call_count == 0


####################################################
#     Tests for plain callables as handlers        #
####################################################


class AsyncCallable:
    r"""Implements a callable object with an ``async def __call__``."""

    def __init__(self, calls: list[dict[str, Any]]) -> None:
        self._calls = calls

    async def __call__(self, context: Context) -> None:
        self._calls.append(dict(context))


class SyncCallable:
    r"""Implements a callable object with a synchronous ``__call__``."""

    def __init__(self, calls: list[dict[str, Any]]) -> None:
        self._calls = calls

    def __call__(self, context: Context) -> None:
        self._calls.append(dict(context))


async def test_event_manager_atrigger_event_awaits_plain_coroutine_function() -> None:
    manager = EventManager()
    values: list[str] = []
    manager.add_event_handler("my_event", functools.partial(append_async, values, "a"))
    await manager.atrigger_event("my_event")
    assert values == ["a"]


async def test_event_manager_atrigger_event_awaits_async_callable_object() -> None:
    manager = EventManager()
    calls: list[dict[str, Any]] = []
    manager.add_event_handler("my_event", AsyncCallable(calls))
    await manager.atrigger_event("my_event", {"epoch": 3})
    assert calls == [{"epoch": 3}]


async def test_event_manager_atrigger_event_sync_callable_object() -> None:
    manager = EventManager()
    calls: list[dict[str, Any]] = []
    manager.add_event_handler("my_event", SyncCallable(calls))
    await manager.atrigger_event("my_event", {"epoch": 3})
    assert calls == [{"epoch": 3}]


def test_event_manager_trigger_event_sync_callable_object() -> None:
    manager = EventManager()
    calls: list[dict[str, Any]] = []
    manager.add_event_handler("my_event", SyncCallable(calls))
    manager.trigger_event("my_event", {"epoch": 3})
    assert calls == [{"epoch": 3}]


def test_event_manager_trigger_event_async_callable_object_raises() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", AsyncCallable([]))
    with pytest.raises(TypeError, match=r"returned an awaitable; use atrigger_event"):
        manager.trigger_event("my_event")


def test_event_manager_trigger_event_async_callable_object_is_not_called_twice() -> None:
    manager = EventManager()
    calls: list[dict[str, Any]] = []
    manager.add_event_handler("my_event", AsyncCallable(calls))
    with pytest.raises(TypeError, match=r"returned an awaitable; use atrigger_event"):
        manager.trigger_event("my_event")
    assert calls == []


def test_event_manager_trigger_event_plain_coroutine_function_raises() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", async_handler)
    with pytest.raises(TypeError, match=r"returned an awaitable; use atrigger_event"):
        manager.trigger_event("my_event")


def test_event_manager_trigger_event_awaitable_error_has_note() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", async_handler)
    with pytest.raises(TypeError, match=r"returned an awaitable") as exc_info:
        manager.trigger_event("my_event")
    assert exc_info.value.__notes__ == [
        "raised by async_handler while handling the event 'my_event'"
    ]


async def test_event_manager_atrigger_event_partial_error_note_names_function() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", functools.partial(failing_async_handler))
    with pytest.raises(ValueError, match=r"boom") as exc_info:
        await manager.atrigger_event("my_event")
    assert exc_info.value.__notes__ == [
        "raised by failing_async_handler while handling the event 'my_event'"
    ]


async def test_event_manager_atrigger_event_condition_and_context() -> None:
    manager = EventManager()
    values: list[object] = []

    async def record(context: Context) -> None:
        values.append(context["value"])

    manager.add_event_handler("my_event", record, condition=lambda: True)
    await manager.atrigger_event("my_event", {"value": "a", "other": 1})
    assert values == ["a"]


async def test_event_manager_atrigger_event_condition_false_skips_coroutine() -> None:
    manager = EventManager()
    values: list[str] = []
    manager.add_event_handler(
        "my_event", functools.partial(append_async, values, "a"), condition=lambda: False
    )
    await manager.atrigger_event("my_event")
    assert values == []


class AwaitableObject:
    r"""Implements an awaitable that is not a coroutine."""

    def __init__(self, awaited: list[int]) -> None:
        self._awaited = awaited

    def __await__(self) -> Any:
        self._awaited.append(1)
        yield


async def test_event_manager_atrigger_event_awaits_object_with_await() -> None:
    manager = EventManager()
    awaited: list[int] = []
    manager.add_event_handler("my_event", lambda: AwaitableObject(awaited))
    await manager.atrigger_event("my_event")
    assert awaited == [1]


def test_event_manager_trigger_event_object_with_await_raises() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", lambda: AwaitableObject([]))
    with pytest.raises(TypeError, match=r"returned an awaitable; use atrigger_event"):
        manager.trigger_event("my_event")


def test_event_manager_trigger_event_condition_false_does_not_call_coroutine_function() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", async_handler, condition=lambda: False)
    manager.trigger_event("my_event")
    assert async_handler.call_count == 0


async def test_event_manager_atrigger_event_context_coroutine_function() -> None:
    manager = EventManager()
    values: list[object] = []

    async def record(context: Context) -> None:
        values.append(context["value"])

    manager.add_event_handler("my_event", record)
    await manager.atrigger_event("my_event", {"value": "a", "other": 1})
    assert values == ["a"]


async def test_event_manager_atrigger_event_condition_reads_the_payload() -> None:
    manager = EventManager()
    values: list[object] = []

    async def record(context: Context) -> None:
        values.append(context["epoch"])

    manager.add_event_handler("my_event", record, condition=lambda context: context["epoch"] >= 1)
    await manager.atrigger_event("my_event", {"epoch": 0})
    await manager.atrigger_event("my_event", {"epoch": 1})
    assert values == [1]


async def async_never() -> bool:
    r"""Implement an async condition that is ``False``."""
    return False


async def test_event_manager_atrigger_event_condition_returns_awaitable() -> None:
    manager = EventManager()
    condition: Any = async_never
    manager.add_event_handler("my_event", async_handler, condition=condition)
    with pytest.raises(TypeError, match=r"condition async_never returned an awaitable"):
        await manager.atrigger_event("my_event")
    assert async_handler.call_count == 0


async def test_event_manager_atrigger_event_condition_awaitable_keeps_once_registration() -> None:
    manager = EventManager()
    condition: Any = async_never
    subscription = manager.add_event_handler(
        "my_event", async_handler, once=True, condition=condition
    )
    with pytest.raises(TypeError, match=r"returned an awaitable"):
        await manager.atrigger_event("my_event")
    assert subscription.active
