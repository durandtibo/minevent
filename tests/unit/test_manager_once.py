from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

import pytest

from minevent import (
    EventHandler,
    EventManager,
    Subscription,
)
from tests.unit.utils import trace

logger = logging.getLogger(__name__)

EVENTS = ("my_event", "my_other_event")


@trace
def hello_handler() -> None:
    r"""Implements a simple handler that prints hello."""
    logger.info("Hello!")


@trace
def failing_handler() -> None:
    r"""Implements a handler that always fails."""
    msg = "handler failed"
    raise RuntimeError(msg)


@trace
def payload_handler(*args: Any, **kwargs: Any) -> None:
    r"""Implements a handler that accepts any arguments."""
    logger.info("Payload: %s %s", args, kwargs)


############################################
#     Tests for subscriptions and once     #
############################################


def test_event_manager_add_event_handler_returns_subscription() -> None:
    manager = EventManager()
    assert isinstance(
        manager.add_event_handler("my_event", EventHandler(hello_handler)), Subscription
    )


def test_event_manager_add_event_handler_subscription_event() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(hello_handler))
    assert subscription.event == "my_event"


def test_event_manager_subscription_remove() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(hello_handler))
    assert subscription.remove()


def test_event_manager_subscription_remove_unregisters_event() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(hello_handler)).remove()
    assert manager.events == []


def test_event_manager_subscription_remove_second_registration() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(hello_handler))
    subscription = manager.add_event_handler("my_event", EventHandler(payload_handler))
    subscription.remove()
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


def test_event_manager_subscription_remove_stops_trigger() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(hello_handler)).remove()
    manager.trigger_event("my_event")
    assert not hello_handler.called


def test_event_manager_subscription_remove_only_removes_own_registration() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(hello_handler))
    manager.add_event_handler("my_event", EventHandler(hello_handler))
    subscription.remove()
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


def test_event_manager_subscription_remove_same_handler_instance_twice() -> None:
    manager = EventManager()
    handler = EventHandler(hello_handler)
    subscription = manager.add_event_handler("my_event", handler)
    manager.add_event_handler("my_event", handler)
    subscription.remove()
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


def test_event_manager_subscription_remove_twice() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(hello_handler))
    subscription.remove()
    assert not subscription.remove()


def test_event_manager_subscription_remove_after_clear_event() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(hello_handler))
    manager.clear_event("my_event")
    assert not subscription.remove()


def test_event_manager_subscription_remove_keeps_other_events() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(hello_handler))
    manager.add_event_handler("my_event", EventHandler(print))
    subscription.remove()
    assert manager.events == ["my_event"]


def test_event_manager_add_event_handler_once_runs_once() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(hello_handler), once=True)
    manager.trigger_event("my_event")
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


def test_event_manager_add_event_handler_once_removed_after_trigger() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(hello_handler), once=True)
    manager.trigger_event("my_event")
    assert manager.events == []


def test_event_manager_add_event_handler_once_receives_payload() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(payload_handler), once=True)
    manager.trigger_event("my_event", epoch=2)
    assert payload_handler.kwargs == {"epoch": 2}


def test_event_manager_add_event_handler_once_handler_raises() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(failing_handler), once=True)
    with pytest.raises(RuntimeError, match=r"handler failed"):
        manager.trigger_event("my_event")


def test_event_manager_add_event_handler_once_runs_once_when_handler_raises() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(failing_handler), once=True)
    with contextlib.suppress(RuntimeError):
        manager.trigger_event("my_event")
    manager.trigger_event("my_event")
    assert failing_handler.call_count == 1


def test_event_manager_add_event_handler_once_runs_once_when_handler_retriggers() -> None:
    manager = EventManager()

    def retrigger() -> None:
        hello_handler()
        manager.trigger_event("my_event")

    manager.add_event_handler("my_event", EventHandler(retrigger), once=True)
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


def test_event_manager_add_event_handler_once_other_handlers_keep_running() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(hello_handler), once=True)
    manager.add_event_handler("my_event", EventHandler(payload_handler))
    manager.trigger_event("my_event")
    manager.trigger_event("my_event")
    assert payload_handler.call_count == 2


def test_event_manager_add_event_handler_once_subscription_remove_before_trigger() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(hello_handler), once=True)
    subscription.remove()
    manager.trigger_event("my_event")
    assert not hello_handler.called


def test_event_manager_add_event_handler_once_subscription_is_once() -> None:
    manager = EventManager()
    assert manager.add_event_handler("my_event", EventHandler(hello_handler), once=True).once


def test_event_manager_add_event_handler_not_once_subscription_is_not_once() -> None:
    manager = EventManager()
    assert not manager.add_event_handler("my_event", EventHandler(hello_handler)).once


def test_event_manager_once_same_handler_registered_twice_runs_twice() -> None:
    manager = EventManager()
    handler = EventHandler(hello_handler)
    manager.add_event_handler("my_event", handler, once=True)
    manager.add_event_handler("my_event", handler, once=True)
    manager.trigger_event("my_event")
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 2


def test_event_manager_once_removed_by_subscription_before_trigger_does_not_run() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(hello_handler), once=True)
    subscription.remove()
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 0


def test_event_manager_atrigger_event_once_runs_once() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(hello_handler), once=True)
    asyncio.run(manager.atrigger_event("my_event"))
    asyncio.run(manager.atrigger_event("my_event"))
    assert hello_handler.call_count == 1


def test_event_manager_add_event_handler_once_removed_when_condition_false() -> None:
    manager = EventManager()
    manager.add_event_handler(
        "my_event", EventHandler(hello_handler, condition=lambda: False), once=True
    )
    manager.trigger_event("my_event")
    assert "my_event" not in manager


def test_event_manager_add_event_handler_once_condition_false_does_not_call() -> None:
    manager = EventManager()
    manager.add_event_handler(
        "my_event", EventHandler(hello_handler, condition=lambda: False), once=True
    )
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 0


def test_event_manager_repr_once() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(hello_handler), once=True)
    assert repr(manager) == "EventManager(events={'my_event': 1})"


def test_event_manager_once_removed_by_earlier_handler_of_same_trigger_does_not_run() -> None:
    manager = EventManager()
    subscriptions: list[Subscription] = []

    def remove_once() -> None:
        subscriptions[0].remove()

    manager.add_event_handler("my_event", EventHandler(remove_once))
    subscriptions.append(
        manager.add_event_handler("my_event", EventHandler(hello_handler), once=True)
    )
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 0


def test_event_manager_atrigger_event_once_removed_by_earlier_handler_does_not_run() -> None:
    manager = EventManager()
    subscriptions: list[Subscription] = []

    def remove_once() -> None:
        subscriptions[0].remove()

    manager.add_event_handler("my_event", EventHandler(remove_once))
    subscriptions.append(
        manager.add_event_handler("my_event", EventHandler(hello_handler), once=True)
    )
    asyncio.run(manager.atrigger_event("my_event"))
    assert hello_handler.call_count == 0
