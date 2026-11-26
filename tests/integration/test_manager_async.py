from __future__ import annotations

import asyncio
import functools
from typing import Any

import pytest

from minevent import Context, EventManager


def test_atrigger_event_reads_payload_at_start() -> None:
    """Test that a task of ``atrigger_event`` sees a change made to the
    dict after its creation and before it starts."""
    manager = EventManager()
    epochs: list[int] = []
    manager.add_event_handler("epoch_end", lambda context: epochs.append(context["epoch"]))

    async def main() -> None:
        data = {"epoch": 1}
        task = asyncio.create_task(manager.atrigger_event("epoch_end", data))
        data["epoch"] = 2
        await task

    asyncio.run(main())
    assert epochs == [2]


def test_atrigger_event_keeps_the_payload_of_a_context() -> None:
    """Test that a ``Context`` built before the task fixes the payload at
    the creation of the task."""
    manager = EventManager()
    epochs: list[int] = []
    manager.add_event_handler("epoch_end", lambda context: epochs.append(context["epoch"]))

    async def main() -> None:
        data = {"epoch": 1}
        task = asyncio.create_task(manager.atrigger_event("epoch_end", Context(data)))
        data["epoch"] = 2
        await task

    asyncio.run(main())
    assert epochs == [1]


def test_atrigger_event_reads_registrations_at_start() -> None:
    """Test that a task of ``atrigger_event`` runs a handler added after
    its creation and before it starts."""
    manager = EventManager()
    calls: list[str] = []

    async def main() -> None:
        task = asyncio.create_task(manager.atrigger_event("epoch_end"))
        manager.add_event_handler("epoch_end", lambda: calls.append("added"))
        await task

    asyncio.run(main())
    assert calls == ["added"]


def test_trigger_event_detects_the_coroutine_of_a_cache_after_its_call() -> None:
    """Test that ``trigger_event`` detects the coroutine returned by a
    ``functools.cache`` after its call: the handler before it has run,
    and the ``once`` registration is consumed."""
    manager = EventManager()
    calls: list[str] = []

    async def upload() -> None:
        calls.append("upload")

    manager.add_event_handler("epoch_end", lambda: calls.append("first"))
    cached: Any = functools.cache(upload)
    subscription = manager.add_event_handler("epoch_end", cached, once=True)
    with pytest.raises(TypeError, match=r"upload returned an awaitable; use atrigger_event"):
        manager.trigger_event("epoch_end")
    assert (calls, subscription.active) == (["first"], False)
