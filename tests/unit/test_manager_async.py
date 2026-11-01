from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

import pytest

from minevent import (
    EventHandler,
    EventManager,
)
from minevent.manager import _OnceEventHandler
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


@trace
def hello_handler() -> None:
    r"""Implements a simple handler that prints hello."""
    logger.info("Hello!")


####################################
#     Tests for atrigger_event     #
####################################


@trace
async def async_handler(**kwargs: Any) -> None:
    r"""Implements a coroutine handler that accepts any keyword
    arguments."""
    logger.info("Async payload: %s", kwargs)


def test_event_manager_atrigger_event_awaits_coroutine_handler() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(async_handler))
    asyncio.run(manager.atrigger_event("my_event"))
    assert async_handler.call_count == 1


def test_event_manager_atrigger_event_payload() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(async_handler))
    asyncio.run(manager.atrigger_event("my_event", epoch=3))
    assert async_handler.kwargs == {"epoch": 3}


def test_event_manager_atrigger_event_mixes_sync_and_async_in_order() -> None:
    order: list[str] = []
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(append_async, handler_args=(order, "first")))
    manager.add_event_handler("my_event", EventHandler(order.append, handler_args=("second",)))
    manager.add_event_handler("my_event", EventHandler(append_async, handler_args=(order, "third")))
    asyncio.run(manager.atrigger_event("my_event"))
    assert order == ["first", "second", "third"]


def test_event_manager_atrigger_event_updates_last_triggered_event() -> None:
    manager = EventManager()
    asyncio.run(manager.atrigger_event("my_event"))
    assert manager.last_triggered_event == "my_event"


def test_event_manager_atrigger_event_without_event_handler() -> None:
    asyncio.run(EventManager().atrigger_event("my_event"))


def test_event_manager_atrigger_event_fail_fast() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(async_fail))
    with pytest.raises(RuntimeError, match=r"async failed"):
        asyncio.run(manager.atrigger_event("my_event"))


def test_event_manager_atrigger_event_fail_fast_skips_next_handlers() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(async_fail))
    manager.add_event_handler("my_event", EventHandler(hello_handler))
    with contextlib.suppress(RuntimeError):
        asyncio.run(manager.atrigger_event("my_event"))
    assert hello_handler.call_count == 0


def test_event_manager_atrigger_event_incorrect_event() -> None:
    bad: Any = 1
    with pytest.raises(TypeError, match=r"event must be a str"):
        asyncio.run(EventManager().atrigger_event(bad))


def test_event_manager_atrigger_event_once() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(async_handler), once=True)
    asyncio.run(manager.atrigger_event("my_event"))
    asyncio.run(manager.atrigger_event("my_event"))
    assert async_handler.call_count == 1


def test_event_manager_atrigger_event_snapshot() -> None:
    manager = EventManager()

    async def add_handler() -> None:
        manager.add_event_handler("my_event", EventHandler(async_handler))

    manager.add_event_handler("my_event", EventHandler(add_handler))
    asyncio.run(manager.atrigger_event("my_event"))
    assert async_handler.call_count == 0


def test_event_manager_start_trigger_returns_snapshot() -> None:
    manager = EventManager()
    handler = EventHandler(hello_handler)
    manager.add_event_handler("my_event", handler)
    assert manager._start_trigger("my_event") == (handler,)


def test_event_manager_start_trigger_sets_last_triggered_event() -> None:
    manager = EventManager()
    manager._start_trigger("my_event")
    assert manager.last_triggered_event == "my_event"


def test_event_manager_start_trigger_incorrect_event() -> None:
    bad: Any = 1
    with pytest.raises(TypeError, match=r"event must be a str"):
        EventManager()._start_trigger(bad)


def test_once_event_handler_ahandle_without_subscription() -> None:
    asyncio.run(_OnceEventHandler(EventHandler(async_handler)).ahandle())
    assert async_handler.call_count == 1


############################################################
#     Tests for trigger_event with a coroutine handler     #
############################################################


def test_event_manager_trigger_event_coroutine_handler_raises() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(async_handler))
    with pytest.raises(TypeError, match=r"returned an awaitable; use ahandle or atrigger_event"):
        manager.trigger_event("my_event")
