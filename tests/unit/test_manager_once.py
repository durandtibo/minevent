from __future__ import annotations

import logging
from typing import Any

import pytest

from minevent import (
    AfterNCondition,
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


def trigger_n_times(manager: EventManager, n_triggers: int) -> None:
    r"""Triggers ``my_event`` ``n_triggers`` times."""
    for _ in range(n_triggers):
        manager.trigger_event("my_event")


@trace
def payload_handler(*args: Any, **kwargs: Any) -> None:
    r"""Implements a handler that accepts any arguments."""
    logger.info("Payload: %s %s", args, kwargs)


############################################
#     Tests for subscriptions and once     #
############################################


def test_event_manager_add_event_handler_returns_subscription() -> None:
    manager = EventManager()
    assert isinstance(manager.add_event_handler("my_event", hello_handler), Subscription)


def test_event_manager_add_event_handler_subscription_event() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", hello_handler)
    assert subscription.event == "my_event"


def test_event_manager_subscription_remove() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", hello_handler)
    assert subscription.remove()


def test_event_manager_subscription_remove_unregisters_event() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler).remove()
    assert manager.events == []


def test_event_manager_subscription_remove_second_registration() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler)
    subscription = manager.add_event_handler("my_event", payload_handler)
    subscription.remove()
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


def test_event_manager_subscription_remove_stops_trigger() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler).remove()
    manager.trigger_event("my_event")
    assert not hello_handler.called


def test_event_manager_subscription_remove_only_removes_own_registration() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", hello_handler)
    manager.add_event_handler("my_event", hello_handler)
    subscription.remove()
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


def test_event_manager_subscription_remove_same_handler_instance_twice() -> None:
    manager = EventManager()
    handler = hello_handler
    subscription = manager.add_event_handler("my_event", handler)
    manager.add_event_handler("my_event", handler)
    subscription.remove()
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


def test_event_manager_subscription_remove_twice() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", hello_handler)
    subscription.remove()
    assert not subscription.remove()


def test_event_manager_subscription_remove_after_clear_event() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", hello_handler)
    manager.clear_event("my_event")
    assert not subscription.remove()


def test_event_manager_subscription_remove_keeps_other_events() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", hello_handler)
    manager.add_event_handler("my_event", print)
    subscription.remove()
    assert manager.events == ["my_event"]


def test_event_manager_add_event_handler_once_runs_once() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler, once=True)
    manager.trigger_event("my_event")
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


def test_event_manager_add_event_handler_once_removed_after_trigger() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler, once=True)
    manager.trigger_event("my_event")
    assert manager.events == []


def test_event_manager_add_event_handler_once_receives_payload() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler, once=True)
    manager.trigger_event("my_event", epoch=2)
    assert payload_handler.args == ({"epoch": 2},)


def test_event_manager_add_event_handler_once_handler_raises() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", failing_handler, once=True)
    with pytest.raises(RuntimeError, match=r"handler failed"):
        manager.trigger_event("my_event")


def test_event_manager_add_event_handler_once_runs_once_when_handler_raises() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", failing_handler, once=True)
    with pytest.raises(RuntimeError, match=r"handler failed"):
        manager.trigger_event("my_event")
    manager.trigger_event("my_event")
    assert failing_handler.call_count == 1


def test_event_manager_add_event_handler_once_runs_once_when_handler_retriggers() -> None:
    manager = EventManager()

    def retrigger() -> None:
        hello_handler()
        manager.trigger_event("my_event")

    manager.add_event_handler("my_event", retrigger, once=True)
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


def test_event_manager_add_event_handler_once_other_handlers_keep_running() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler, once=True)
    manager.add_event_handler("my_event", payload_handler)
    manager.trigger_event("my_event")
    manager.trigger_event("my_event")
    assert payload_handler.call_count == 2


def test_event_manager_add_event_handler_once_subscription_remove_before_trigger() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", hello_handler, once=True)
    subscription.remove()
    manager.trigger_event("my_event")
    assert not hello_handler.called


def test_event_manager_add_event_handler_once_subscription_is_once() -> None:
    manager = EventManager()
    assert manager.add_event_handler("my_event", hello_handler, once=True).once


def test_event_manager_add_event_handler_not_once_subscription_is_not_once() -> None:
    manager = EventManager()
    assert not manager.add_event_handler("my_event", hello_handler).once


def test_event_manager_once_same_handler_registered_twice_runs_twice() -> None:
    manager = EventManager()
    handler = hello_handler
    manager.add_event_handler("my_event", handler, once=True)
    manager.add_event_handler("my_event", handler, once=True)
    manager.trigger_event("my_event")
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 2


def test_event_manager_once_removed_by_subscription_before_trigger_does_not_run() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", hello_handler, once=True)
    subscription.remove()
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 0


async def test_event_manager_atrigger_event_once_runs_once() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler, once=True)
    await manager.atrigger_event("my_event")
    await manager.atrigger_event("my_event")
    assert hello_handler.call_count == 1


def test_once_false_condition_does_not_consume() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler(
        "my_event", hello_handler, condition=lambda: False, once=True
    )
    manager.trigger_event("my_event")
    assert subscription.active


def test_once_false_condition_does_not_call_handler() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler, condition=lambda: False, once=True)
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 0


def test_once_does_not_run_before_condition_is_true() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler, condition=AfterNCondition(2), once=True)
    trigger_n_times(manager, 2)
    assert hello_handler.call_count == 0


def test_once_runs_on_third_trigger_with_after_n_condition() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler, condition=AfterNCondition(2), once=True)
    trigger_n_times(manager, 3)
    assert hello_handler.call_count == 1


def test_once_removed_after_condition_becomes_true() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler, condition=AfterNCondition(2), once=True)
    trigger_n_times(manager, 3)
    assert len(manager) == 0


def test_once_runs_once_when_condition_stays_true() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler, condition=lambda: True, once=True)
    trigger_n_times(manager, 3)
    assert hello_handler.call_count == 1


def test_once_raising_condition_keeps_registration() -> None:
    def condition() -> bool:
        msg = "condition failed"
        raise RuntimeError(msg)

    manager = EventManager()
    subscription = manager.add_event_handler(
        "my_event", hello_handler, condition=condition, once=True
    )
    with pytest.raises(RuntimeError, match=r"condition failed"):
        manager.trigger_event("my_event")
    assert subscription.active


def test_once_raising_handler_consumes_registration() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", failing_handler, once=True)
    with pytest.raises(RuntimeError, match=r"handler failed"):
        manager.trigger_event("my_event")
    assert not subscription.active


async def test_once_false_condition_does_not_consume_async() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler(
        "my_event", hello_handler, condition=lambda: False, once=True
    )
    await manager.atrigger_event("my_event")
    assert subscription.active


def test_event_manager_repr_once() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler, once=True)
    assert repr(manager) == "EventManager(events={'my_event': 1})"


def test_event_manager_once_removed_by_earlier_handler_of_same_trigger_does_not_run() -> None:
    manager = EventManager()
    subscriptions: list[Subscription] = []

    def remove_once() -> None:
        subscriptions[0].remove()

    manager.add_event_handler("my_event", remove_once)
    subscriptions.append(manager.add_event_handler("my_event", hello_handler, once=True))
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 0


async def test_event_manager_atrigger_event_once_removed_by_earlier_handler_does_not_run() -> None:
    manager = EventManager()
    subscriptions: list[Subscription] = []

    def remove_once() -> None:
        subscriptions[0].remove()

    manager.add_event_handler("my_event", remove_once)
    subscriptions.append(manager.add_event_handler("my_event", hello_handler, once=True))
    await manager.atrigger_event("my_event")
    assert hello_handler.call_count == 0
