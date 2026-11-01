from __future__ import annotations

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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
