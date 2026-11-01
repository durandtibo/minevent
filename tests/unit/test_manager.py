from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from minevent import EventHandler, EventManager
from tests.unit.utils import trace

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

EVENTS = ("my_event", "my_other_event")


@trace
def hello_handler() -> None:
    r"""Implements a simple handler that prints hello."""
    logger.info("Hello!")


@pytest.fixture(autouse=True)
def _reset_tracer() -> None:
    def reset_func(func: Callable) -> None:
        func.called = False
        func.call_count = 0
        func.args = ()
        func.kwargs = {}

    reset_func(hello_handler)


##################################
#     Tests for EventManager     #
##################################


def test_event_manager_str_without_event_handler() -> None:
    assert str(EventManager()).startswith("EventManager(")


def test_event_manager_str_with_event_handler() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    assert str(event_manager).startswith("EventManager(")


def test_event_manager_last_triggered_event_none() -> None:
    assert EventManager().last_triggered_event is None


def test_last_triggered_event_name_after_fire() -> None:
    event_manager = EventManager()
    event_manager.trigger_event("my_event")
    assert event_manager.last_triggered_event == "my_event"
    event_manager.trigger_event("my_other_event")
    assert event_manager.last_triggered_event == "my_other_event"
    event_manager.trigger_event("my_event")
    assert event_manager.last_triggered_event == "my_event"


def test_event_manager_last_triggered_event() -> None:
    event_manager = EventManager()
    event_manager.trigger_event("my_event")
    event_manager.trigger_event("my_other_event")
    assert event_manager.last_triggered_event == "my_other_event"


@pytest.mark.parametrize("event", EVENTS)
def test_event_manager_add_event_handler_event(event: str) -> None:
    event_manager = EventManager()
    event_manager.add_event_handler(event, EventHandler(hello_handler))
    event_manager.trigger_event(event)
    assert hello_handler.call_count == 1


def test_event_manager_add_event_handler_duplicate_event_handlers() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    event_manager.trigger_event("my_event")
    assert hello_handler.call_count == 2


@pytest.mark.parametrize("event", EVENTS)
def test_event_manager_trigger_event(event: str) -> None:
    event_manager = EventManager()
    event_manager.add_event_handler(event, EventHandler(hello_handler))
    event_manager.trigger_event(event)
    assert hello_handler.called
    assert hello_handler.call_count == 1


def test_event_manager_trigger_event_2_times() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    event_manager.trigger_event("my_event")
    event_manager.trigger_event("my_event")
    assert hello_handler.called
    assert hello_handler.call_count == 2


def test_event_manager_trigger_event_without_event_handler() -> None:
    event_manager = EventManager()
    event_manager.trigger_event("my_event")
    assert event_manager.last_triggered_event == "my_event"


def test_event_manager_has_event_handler_true() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    assert event_manager.has_event_handler(EventHandler(hello_handler))


def test_event_manager_has_event_handler_true_with_event() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    assert event_manager.has_event_handler(EventHandler(hello_handler), event="my_event")


def test_event_manager_has_event_handler_false() -> None:
    event_manager = EventManager()
    assert not event_manager.has_event_handler(EventHandler(hello_handler))


def test_event_manager_has_event_handler_false_with_event() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(lambda: True))
    event_manager.add_event_handler("my_other_event", EventHandler(hello_handler))
    assert not event_manager.has_event_handler(EventHandler(hello_handler), event="my_event")


@pytest.mark.parametrize("event", EVENTS)
def test_event_manager_remove_event_handler(event: str) -> None:
    event_manager = EventManager()
    event_manager.add_event_handler(event, EventHandler(hello_handler))
    event_manager.remove_event_handler(event, EventHandler(hello_handler))
    assert not event_manager.has_event_handler(EventHandler(hello_handler), event)


def test_event_manager_remove_event_handler_duplicate_handler() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    event_manager.add_event_handler("my_event", EventHandler(lambda: True))
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    event_manager.remove_event_handler("my_event", EventHandler(hello_handler))
    assert not event_manager.has_event_handler(EventHandler(hello_handler))


def test_event_manager_remove_event_handler_multiple_events() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    event_manager.add_event_handler("my_other_event", EventHandler(hello_handler))
    event_manager.remove_event_handler("my_event", EventHandler(hello_handler))
    assert not event_manager.has_event_handler(EventHandler(hello_handler), "my_event")
    assert event_manager.has_event_handler(EventHandler(hello_handler), "my_other_event")


def test_event_manager_remove_event_handler_missing_event() -> None:
    event_manager = EventManager()
    with pytest.raises(RuntimeError, match=r"'my_event' event does not exist"):
        event_manager.remove_event_handler("my_event", EventHandler(hello_handler))


def test_event_manager_remove_event_handler_missing_handler() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(lambda: True))
    with pytest.raises(
        RuntimeError, match=r"is not found among registered event handlers for 'my_event' event"
    ):
        event_manager.remove_event_handler("my_event", EventHandler(hello_handler))


def test_event_manager_reset() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    event_manager.add_event_handler("my_other_event", EventHandler(hello_handler))
    event_manager.trigger_event("my_event")
    event_manager.reset()
    assert not event_manager.has_event_handler(EventHandler(hello_handler))
    assert event_manager.last_triggered_event is None


def test_event_manager_reset_empty() -> None:
    event_manager = EventManager()
    assert not event_manager.has_event_handler(EventHandler(hello_handler))
    assert event_manager.last_triggered_event is None


def test_event_manager_no_duplicate() -> None:
    event_manager = EventManager()
    for _ in range(5):
        event_handler = EventHandler(hello_handler)
        if not event_manager.has_event_handler(event_handler, "my_event"):
            event_manager.add_event_handler("my_event", event_handler)
    event_manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


def test_event_manager_trigger_event_does_not_register_event() -> None:
    event_manager = EventManager()
    event_manager.trigger_event("my_event")
    assert "my_event:" not in str(event_manager)


def test_event_manager_has_event_handler_does_not_register_event() -> None:
    event_manager = EventManager()
    assert not event_manager.has_event_handler(EventHandler(hello_handler), "my_event")
    assert "my_event:" not in str(event_manager)


def test_event_manager_remove_event_handler_after_trigger() -> None:
    event_manager = EventManager()
    event_manager.trigger_event("my_event")
    with pytest.raises(RuntimeError, match=r"'my_event' event does not exist"):
        event_manager.remove_event_handler("my_event", EventHandler(hello_handler))


def test_event_manager_has_event_handler_empty_event_name() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    assert not event_manager.has_event_handler(EventHandler(hello_handler), event="")
    event_manager.add_event_handler("", EventHandler(hello_handler))
    assert event_manager.has_event_handler(EventHandler(hello_handler), event="")


def test_event_manager_trigger_event_handler_added_during_dispatch_runs_next_time() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler(
        "my_event",
        EventHandler(
            lambda: event_manager.add_event_handler("my_event", EventHandler(hello_handler))
        ),
    )
    event_manager.trigger_event("my_event")
    assert hello_handler.call_count == 0
    event_manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


def test_event_manager_trigger_event_handler_removed_during_dispatch_still_runs() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler(
        "my_event",
        EventHandler(
            lambda: event_manager.remove_event_handler("my_event", EventHandler(hello_handler))
        ),
    )
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    event_manager.trigger_event("my_event")
    assert hello_handler.call_count == 1
    assert not event_manager.has_event_handler(EventHandler(hello_handler))


def test_event_manager_trigger_event_handler_raises_skips_next_handlers() -> None:
    def fail() -> None:
        msg = "boom"
        raise ValueError(msg)

    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(fail))
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    with pytest.raises(ValueError, match=r"boom"):
        event_manager.trigger_event("my_event")
    assert hello_handler.call_count == 0
    assert event_manager.last_triggered_event == "my_event"


def test_event_manager_last_triggered_event_set_before_handlers_run() -> None:
    event_manager = EventManager()
    seen = []
    event_manager.add_event_handler(
        "my_event", EventHandler(lambda: seen.append(event_manager.last_triggered_event))
    )
    event_manager.trigger_event("my_event")
    assert seen == ["my_event"]
