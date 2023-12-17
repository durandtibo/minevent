from __future__ import annotations

import logging

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


def main() -> None:
    check_event_manager()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
