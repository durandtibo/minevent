from __future__ import annotations

import contextlib
import logging
from typing import Any

import pytest

from minevent import (
    EventHandler,
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
async def async_handler(**kwargs: Any) -> None:
    r"""Implements a coroutine handler that accepts any keyword
    arguments."""
    logger.info("Async payload: %s", kwargs)


async def test_event_manager_atrigger_event_awaits_coroutine_handler() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(async_handler))
    await manager.atrigger_event("my_event")
    assert async_handler.call_count == 1


async def test_event_manager_atrigger_event_payload() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(async_handler))
    await manager.atrigger_event("my_event", epoch=3)
    assert async_handler.kwargs == {"epoch": 3}


async def test_event_manager_atrigger_event_mixes_sync_and_async_in_order() -> None:
    order: list[str] = []
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(append_async, handler_args=(order, "first")))
    manager.add_event_handler("my_event", EventHandler(order.append, handler_args=("second",)))
    manager.add_event_handler("my_event", EventHandler(append_async, handler_args=(order, "third")))
    await manager.atrigger_event("my_event")
    assert order == ["first", "second", "third"]


async def test_event_manager_atrigger_event_without_event_handler() -> None:
    await EventManager().atrigger_event("my_event")


async def test_event_manager_atrigger_event_fail_fast() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(async_fail))
    with pytest.raises(RuntimeError, match=r"async failed"):
        await manager.atrigger_event("my_event")


async def test_event_manager_atrigger_event_fail_fast_skips_next_handlers() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(async_fail))
    manager.add_event_handler("my_event", EventHandler(hello_handler))
    with contextlib.suppress(RuntimeError):
        await manager.atrigger_event("my_event")
    assert hello_handler.call_count == 0


async def test_event_manager_atrigger_event_incorrect_event() -> None:
    bad: Any = 1
    with pytest.raises(TypeError, match=r"event must be a str"):
        await EventManager().atrigger_event(bad)


async def test_event_manager_atrigger_event_once() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(async_handler), once=True)
    await manager.atrigger_event("my_event")
    await manager.atrigger_event("my_event")
    assert async_handler.call_count == 1


async def test_event_manager_atrigger_event_snapshot() -> None:
    manager = EventManager()

    async def add_handler() -> None:
        manager.add_event_handler("my_event", EventHandler(async_handler))

    manager.add_event_handler("my_event", EventHandler(add_handler))
    await manager.atrigger_event("my_event")
    assert async_handler.call_count == 0


############################################################
#     Tests for trigger_event with a coroutine handler     #
############################################################


def test_event_manager_trigger_event_coroutine_handler_raises() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(async_handler))
    with pytest.raises(TypeError, match=r"returned an awaitable; use ahandle or atrigger_event"):
        manager.trigger_event("my_event")


async def test_event_manager_atrigger_event_handler_raises_adds_note() -> None:
    manager = EventManager()
    handler = EventHandler(failing_async_handler)
    manager.add_event_handler("my_event", handler)
    with pytest.raises(ValueError, match=r"boom") as exc_info:
        await manager.atrigger_event("my_event")
    assert exc_info.value.__notes__ == [
        "raised by failing_async_handler while handling the event 'my_event'"
    ]


async def test_event_manager_atrigger_event_on_filter_payload() -> None:
    manager = EventManager()
    epochs: list[int] = []

    @manager.on("my_event", filter_payload=True)
    async def log_epoch(epoch: int) -> None:
        epochs.append(epoch)

    await manager.atrigger_event("my_event", epoch=3, loss=0.5)
    assert epochs == [3]


async def test_event_manager_atrigger_event_on_condition_false() -> None:
    manager = EventManager()
    manager.on("my_event", condition=lambda: False)(async_handler)
    await manager.atrigger_event("my_event")
    assert async_handler.call_count == 0
