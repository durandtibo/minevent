from __future__ import annotations

import asyncio
import functools
from typing import TYPE_CHECKING, Any

import pytest

from minevent import Context, EventManager

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


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
    """Test that a ``Context`` built before the task fixes the payload
    at the creation of the task."""
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
        manager.add_event_handler("epoch_end", lambda _: calls.append("added"))
        await task

    asyncio.run(main())
    assert calls == ["added"]


async def run_trigger_event(manager: EventManager, event: str) -> None:
    r"""Trigger an event with ``trigger_event``, inside an event
    loop."""
    manager.trigger_event(event)


@pytest.mark.parametrize("trigger", [run_trigger_event, EventManager.atrigger_event])
def test_handler_starts_a_background_task(
    trigger: Callable[[EventManager, str], Awaitable[None]],
) -> None:
    """Test that a handler that returns nothing leaves its task running
    after the trigger."""
    manager = EventManager()
    calls: list[str] = []
    tasks: list[asyncio.Task[None]] = []

    async def upload() -> None:
        await asyncio.sleep(0)
        calls.append("upload")

    def start_upload(_: Context) -> None:
        tasks.append(asyncio.get_running_loop().create_task(upload()))

    manager.add_event_handler("checkpoint_saved", start_upload)

    async def main() -> None:
        await trigger(manager, "checkpoint_saved")
        calls.append("after the trigger")
        await asyncio.gather(*tasks)

    asyncio.run(main())
    assert calls == ["after the trigger", "upload"]


def test_trigger_event_detects_the_coroutine_of_a_wrapper_after_its_call() -> None:
    """Test that ``trigger_event`` detects the coroutine returned by a
    synchronous ``functools.wraps`` wrapper after its call: the handler
    before it has run, and the ``once`` registration is consumed."""
    manager = EventManager()
    calls: list[str] = []

    async def upload(_: Context) -> None:
        calls.append("upload")

    @functools.wraps(upload)
    def wrapper(context: Context) -> object:
        return upload(context)

    manager.add_event_handler("epoch_end", lambda _: calls.append("first"))
    subscription = manager.add_event_handler("epoch_end", wrapper, once=True)
    with pytest.raises(TypeError, match=r"upload returned an awaitable; use atrigger_event"):
        manager.trigger_event("epoch_end")
    assert (calls, subscription.active) == (["first"], False)


def test_cached_handler_cannot_hash_the_context() -> None:
    """Test that a ``functools.cache`` handler is registered, and raises
    at the trigger because a ``Context`` is not hashable."""
    manager = EventManager()

    def log_epoch(_: object) -> None:
        pass

    # Typed ``Any``: a type checker reports that the context is not hashable.
    cached: Any = functools.cache(log_epoch)
    manager.add_event_handler("epoch_end", cached)
    with pytest.raises(TypeError, match=r"unhashable type: 'Context'"):
        manager.trigger_event("epoch_end")


def test_atrigger_event_stop_iteration_has_the_noted_cause() -> None:
    """Test that the ``RuntimeError`` of ``atrigger_event`` has the
    ``StopIteration`` of the handler, with its note, as cause."""
    manager = EventManager()

    def stop(_: Context) -> None:
        msg = "stop"
        raise StopIteration(msg)

    manager.add_event_handler("epoch_end", stop)
    with pytest.raises(RuntimeError, match=r"coroutine raised StopIteration") as exc_info:
        asyncio.run(manager.atrigger_event("epoch_end"))
    assert getattr(exc_info.value.__cause__, "__notes__", None) == [
        (
            "raised by test_atrigger_event_stop_iteration_has_the_noted_cause.<locals>.stop "
            "while handling the event 'epoch_end'"
        )
    ]
