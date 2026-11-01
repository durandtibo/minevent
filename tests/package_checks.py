from __future__ import annotations

import asyncio
import logging

import minevent
from minevent import EventHandler, EventManager

logger = logging.getLogger(__name__)


def check_event_manager() -> None:
    logger.info("Checking event manager...")

    event_manager = EventManager()
    event_manager.add_event_handler(event="my_event", event_handler=EventHandler(print, ["Hello!"]))
    event_manager.trigger_event("my_event")
    assert event_manager.has_event_handler(
        event="my_event", event_handler=EventHandler(print, ["Hello!"])
    )


def check_once() -> None:
    logger.info("Checking once...")

    calls: list[int] = []
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(calls.append, [1]), once=True)
    event_manager.trigger_event("my_event")
    event_manager.trigger_event("my_event")
    assert calls == [1]
    assert "my_event" not in event_manager


def check_payload() -> None:
    logger.info("Checking payload...")

    received: list[dict[str, object]] = []

    def handler(**kwargs: object) -> None:
        received.append(kwargs)

    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(handler))
    event_manager.trigger_event("my_event", epoch=3, event="batch_end")
    assert received == [{"epoch": 3, "event": "batch_end"}]


def check_subscription() -> None:
    logger.info("Checking subscription...")

    calls: list[int] = []
    event_manager = EventManager()
    subscription = event_manager.add_event_handler("my_event", EventHandler(calls.append, [1]))
    assert subscription.active
    assert subscription.remove()
    event_manager.trigger_event("my_event")
    assert calls == []
    assert not subscription.active


def check_async_trigger() -> None:
    logger.info("Checking atrigger_event...")

    calls: list[int] = []

    async def handler(value: int) -> None:
        calls.append(value)

    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(handler))
    asyncio.run(event_manager.atrigger_event("my_event", value=7))
    assert calls == [7]


def check_exports() -> None:
    logger.info("Checking exports...")
    for name in minevent.__all__:
        assert hasattr(minevent, name), f"missing export: {name}"


def check_version() -> None:
    logger.info("Checking version...")
    assert minevent.__version__ != "0.0.0"


def main() -> None:
    check_exports()
    check_version()
    check_event_manager()
    check_once()
    check_payload()
    check_subscription()
    check_async_trigger()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
