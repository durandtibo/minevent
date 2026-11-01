from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any, cast

import pytest

from minevent import (
    EventHandler,
    EventManager,
    Subscription,
)
from minevent.manager import _OnceEventHandler, _unwrap
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


def test_event_manager_add_event_handler_once_registers_wrapper() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(hello_handler), once=True)
    assert isinstance(manager._event_handlers["my_event"][0], _OnceEventHandler)


def test_event_manager_add_event_handler_once_has_subscription_when_visible() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(hello_handler), once=True)
    registered = cast("_OnceEventHandler", manager._event_handlers["my_event"][0])
    assert registered.subscription is not None


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


def test_event_manager_has_event_handler_once_true() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(hello_handler), once=True)
    assert manager.has_event_handler(EventHandler(hello_handler), "my_event")


def test_event_manager_remove_event_handler_once() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(hello_handler), once=True)
    manager.remove_event_handler("my_event", EventHandler(hello_handler))
    assert manager.events == []


def test_event_manager_repr_once() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(hello_handler), once=True)
    assert "_OnceEventHandler(EventHandler(" in repr(manager)


#######################################
#     Tests for _OnceEventHandler     #
#######################################


def test_once_event_handler_equal_true_with_wrapped_equal_handler() -> None:
    assert _OnceEventHandler(EventHandler(hello_handler)).equal(EventHandler(hello_handler))


def test_once_event_handler_equal_true_with_other_once() -> None:
    assert _OnceEventHandler(EventHandler(hello_handler)).equal(
        _OnceEventHandler(EventHandler(hello_handler))
    )


def test_once_event_handler_equal_false() -> None:
    assert not _OnceEventHandler(EventHandler(hello_handler)).equal(EventHandler(print))


def test_once_event_handler_handle_without_subscription() -> None:
    _OnceEventHandler(EventHandler(hello_handler)).handle()
    assert hello_handler.call_count == 1


def test_once_event_handler_handle_skips_when_already_removed() -> None:
    handler = _OnceEventHandler(EventHandler(hello_handler))
    handler.subscription = Subscription("my_event", handler, lambda _event, _handler: False)
    handler.handle()
    assert hello_handler.call_count == 0


def test_once_event_handler_handle_runs_when_removal_succeeds() -> None:
    handler = _OnceEventHandler(EventHandler(hello_handler))
    handler.subscription = Subscription("my_event", handler, lambda _event, _handler: True)
    handler.handle()
    assert hello_handler.call_count == 1


def test_once_event_handler_ahandle_skips_when_already_removed() -> None:
    handler = _OnceEventHandler(EventHandler(hello_handler))
    handler.subscription = Subscription("my_event", handler, lambda _event, _handler: False)
    asyncio.run(handler.ahandle())
    assert hello_handler.call_count == 0


def test_once_event_handler_ahandle_runs_when_removal_succeeds() -> None:
    handler = _OnceEventHandler(EventHandler(hello_handler))
    handler.subscription = Subscription("my_event", handler, lambda _event, _handler: True)
    asyncio.run(handler.ahandle())
    assert hello_handler.call_count == 1


def test_once_event_handler_repr() -> None:
    assert repr(_OnceEventHandler(EventHandler(hello_handler))).startswith(
        "_OnceEventHandler(EventHandler("
    )


#############################
#     Tests for _unwrap     #
#############################


def test_unwrap_once_event_handler() -> None:
    handler = EventHandler(hello_handler)
    assert _unwrap(_OnceEventHandler(handler)) is handler


def test_unwrap_other_event_handler() -> None:
    handler = EventHandler(hello_handler)
    assert _unwrap(handler) is handler
