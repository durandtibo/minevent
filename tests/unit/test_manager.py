from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

import pytest

from minevent import (
    BaseCondition,
    BaseEventHandler,
    EventHandler,
    EventManager,
    PeriodicCondition,
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


@pytest.fixture(autouse=True)
def _reset_tracer() -> None:
    hello_handler.reset()
    payload_handler.reset()
    failing_handler.reset()
    async_handler.reset()


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


def test_event_manager_last_triggered_event_after_trigger() -> None:
    event_manager = EventManager()
    event_manager.trigger_event("my_event")
    assert event_manager.last_triggered_event == "my_event"
    event_manager.trigger_event("my_other_event")
    assert event_manager.last_triggered_event == "my_other_event"
    event_manager.trigger_event("my_event")
    assert event_manager.last_triggered_event == "my_event"


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
    with pytest.raises(ValueError, match=r"'my_event' event does not exist"):
        event_manager.remove_event_handler("my_event", EventHandler(hello_handler))


def test_event_manager_remove_event_handler_missing_handler() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(lambda: True))
    with pytest.raises(
        ValueError, match=r"is not found among registered event handlers for 'my_event' event"
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
    with pytest.raises(ValueError, match=r"'my_event' event does not exist"):
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


INVALID_EVENTS = [1, None, b"my_event"]


@pytest.mark.parametrize("event", INVALID_EVENTS)
def test_event_manager_add_event_handler_event_must_be_str(event: Any) -> None:
    with pytest.raises(TypeError, match=r"event must be a str"):
        EventManager().add_event_handler(event, EventHandler(hello_handler))


@pytest.mark.parametrize("event", INVALID_EVENTS)
def test_event_manager_trigger_event_event_must_be_str(event: Any) -> None:
    with pytest.raises(TypeError, match=r"event must be a str"):
        EventManager().trigger_event(event)


@pytest.mark.parametrize("event", INVALID_EVENTS)
def test_event_manager_remove_event_handler_event_must_be_str(event: Any) -> None:
    with pytest.raises(TypeError, match=r"event must be a str"):
        EventManager().remove_event_handler(event, EventHandler(hello_handler))


def test_event_manager_has_event_handler_event_must_be_str() -> None:
    event: Any = 1
    with pytest.raises(TypeError, match=r"event must be a str"):
        EventManager().has_event_handler(EventHandler(hello_handler), event=event)


def test_event_manager_remove_event_handler_missing_ok() -> None:
    event_manager = EventManager()
    event_manager.remove_event_handler("my_event", EventHandler(hello_handler), missing_ok=True)
    event_manager.add_event_handler("my_event", EventHandler(lambda: True))
    event_manager.remove_event_handler("my_event", EventHandler(hello_handler), missing_ok=True)
    assert event_manager.has_event_handler(EventHandler(lambda: True), "my_event") is False
    event_manager.trigger_event("my_event")


def test_event_manager_repr_empty() -> None:
    assert repr(EventManager()) == (
        "EventManager(\n  (event_handlers): {}\n  (last_triggered_event): None\n)"
    )


def test_event_manager_repr_with_event_handlers() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    event_manager.trigger_event("my_event")
    out = repr(event_manager)
    assert out == (
        "EventManager(\n"
        "  (event_handlers): \n"
        "    (my_event): \n"
        "      (0): EventHandler(\n"
        f"          (handler): {hello_handler!r}\n"
        "          (handler_args): ()\n"
        "          (handler_kwargs): {}\n"
        "        )\n"
        "  (last_triggered_event): my_event\n"
        ")"
    )


def test_event_manager_events() -> None:
    event_manager = EventManager()
    assert event_manager.events == []
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    event_manager.add_event_handler("my_other_event", EventHandler(hello_handler))
    event_manager.trigger_event("unknown_event")
    assert event_manager.events == ["my_event", "my_other_event"]


def test_event_manager_contains() -> None:
    event_manager = EventManager()
    assert "my_event" not in event_manager
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    assert "my_event" in event_manager
    event_manager.remove_event_handler("my_event", EventHandler(hello_handler))
    assert "my_event" not in event_manager


def test_event_manager_clear_event() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    event_manager.add_event_handler("my_other_event", EventHandler(hello_handler))
    event_manager.clear_event("my_event")
    assert event_manager.events == ["my_other_event"]
    event_manager.trigger_event("my_event")
    assert hello_handler.call_count == 0


def test_event_manager_clear_event_missing() -> None:
    EventManager().clear_event("my_event")


def test_event_manager_clear_event_must_be_str() -> None:
    event: Any = 1
    with pytest.raises(TypeError, match=r"event must be a str"):
        EventManager().clear_event(event)


###########################################
#     Tests for trigger_event payload     #
###########################################


def test_event_manager_trigger_event_payload() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(payload_handler))
    manager.trigger_event("my_event", epoch=3, loss=0.5)
    assert payload_handler.kwargs == {"epoch": 3, "loss": 0.5}


def test_event_manager_trigger_event_payload_all_handlers() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(payload_handler))
    manager.add_event_handler("my_event", EventHandler(payload_handler, handler_args=(1,)))
    manager.trigger_event("my_event", epoch=3)
    assert payload_handler.call_count == 2


def test_event_manager_trigger_event_without_payload() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(payload_handler))
    manager.trigger_event("my_event")
    assert payload_handler.kwargs == {}


def test_event_manager_trigger_event_payload_not_accepted_by_handler() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(hello_handler))
    with pytest.raises(TypeError, match=r"unexpected keyword argument 'epoch'"):
        manager.trigger_event("my_event", epoch=3)


############################################
#     Tests for subscriptions and once     #
############################################


def test_event_manager_add_event_handler_returns_subscription() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(hello_handler))
    assert isinstance(subscription, Subscription)
    assert subscription.event == "my_event"


def test_event_manager_subscription_remove() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(hello_handler))
    assert subscription.remove()
    assert manager.events == []


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


def test_event_manager_add_event_handler_once_runs_once_when_handler_raises() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(failing_handler), once=True)
    with pytest.raises(RuntimeError, match=r"handler failed"):
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


def test_event_manager_add_event_handler_once_has_subscription_when_visible() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(hello_handler), once=True)
    registered = manager._event_handlers["my_event"][0]
    assert isinstance(registered, _OnceEventHandler)
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


#########################
#     Tests for _unwrap #
#########################


def test_unwrap_once_event_handler() -> None:
    handler = EventHandler(hello_handler)
    assert _unwrap(_OnceEventHandler(handler)) is handler


def test_unwrap_other_event_handler() -> None:
    handler = EventHandler(hello_handler)
    assert _unwrap(handler) is handler


def test_event_manager_subscription_remove_second_registration() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(hello_handler))
    subscription = manager.add_event_handler("my_event", EventHandler(payload_handler))
    subscription.remove()
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


####################################
#     Tests for atrigger_event     #
####################################


@trace
async def async_handler(**kwargs: Any) -> None:
    r"""Implements a coroutine handler that accepts any keyword
    arguments."""
    logger.info("Async payload: %s", kwargs)


def test_event_manager_atrigger_event_awaits_coroutine_handler() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(async_handler))
    asyncio.run(manager.atrigger_event("my_event"))
    assert async_handler.call_count == 1


def test_event_manager_atrigger_event_payload() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(async_handler))
    asyncio.run(manager.atrigger_event("my_event", epoch=3))
    assert async_handler.kwargs == {"epoch": 3}


def test_event_manager_atrigger_event_mixes_sync_and_async_in_order() -> None:
    order = []

    async def first() -> None:
        order.append("first")

    def second() -> None:
        order.append("second")

    async def third() -> None:
        order.append("third")

    manager = EventManager()
    for func in (first, second, third):
        manager.add_event_handler("my_event", EventHandler(func))
    asyncio.run(manager.atrigger_event("my_event"))
    assert order == ["first", "second", "third"]


def test_event_manager_atrigger_event_updates_last_triggered_event() -> None:
    manager = EventManager()
    asyncio.run(manager.atrigger_event("my_event"))
    assert manager.last_triggered_event == "my_event"


def test_event_manager_atrigger_event_without_event_handler() -> None:
    asyncio.run(EventManager().atrigger_event("my_event"))


def test_event_manager_atrigger_event_fail_fast() -> None:
    async def failing() -> None:
        msg = "async failed"
        raise RuntimeError(msg)

    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(failing))
    manager.add_event_handler("my_event", EventHandler(hello_handler))
    with pytest.raises(RuntimeError, match=r"async failed"):
        asyncio.run(manager.atrigger_event("my_event"))
    assert hello_handler.call_count == 0


def test_event_manager_atrigger_event_incorrect_event() -> None:
    bad: Any = 1
    with pytest.raises(TypeError, match=r"event must be a str"):
        asyncio.run(EventManager().atrigger_event(bad))


def test_event_manager_atrigger_event_once() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(async_handler), once=True)
    asyncio.run(manager.atrigger_event("my_event"))
    asyncio.run(manager.atrigger_event("my_event"))
    assert async_handler.call_count == 1


def test_event_manager_atrigger_event_snapshot() -> None:
    manager = EventManager()

    async def add_handler() -> None:
        manager.add_event_handler("my_event", EventHandler(async_handler))

    manager.add_event_handler("my_event", EventHandler(add_handler))
    asyncio.run(manager.atrigger_event("my_event"))
    assert async_handler.call_count == 0


def test_event_manager_start_trigger_returns_snapshot() -> None:
    manager = EventManager()
    handler = EventHandler(hello_handler)
    manager.add_event_handler("my_event", handler)
    assert manager._start_trigger("my_event") == (handler,)


def test_event_manager_start_trigger_sets_last_triggered_event() -> None:
    manager = EventManager()
    manager._start_trigger("my_event")
    assert manager.last_triggered_event == "my_event"


def test_event_manager_start_trigger_incorrect_event() -> None:
    bad: Any = 1
    with pytest.raises(TypeError, match=r"event must be a str"):
        EventManager()._start_trigger(bad)


def test_once_event_handler_ahandle_without_subscription() -> None:
    asyncio.run(_OnceEventHandler(EventHandler(async_handler)).ahandle())
    assert async_handler.call_count == 1


##########################################
#     Tests for real-world scenarios     #
##########################################


class CustomCondition(BaseCondition):
    r"""Implements a condition that is true for odd calls."""

    def __init__(self) -> None:
        self._count = 0

    def equal(self, other: object) -> bool:
        return isinstance(other, CustomCondition)

    def evaluate(self) -> bool:
        self._count += 1
        return self._count % 2 == 1


class CustomHandler(BaseEventHandler):
    r"""Implements a handler that records the payload."""

    def __init__(self, calls: list[dict[str, Any]]) -> None:
        self._calls = calls

    def equal(self, other: object) -> bool:
        return isinstance(other, CustomHandler)

    def handle(self, **payload: Any) -> None:
        self._calls.append(payload)


def test_event_manager_remove_event_handler_after_trigger_event() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    event_manager.trigger_event("my_event")
    event_manager.remove_event_handler("my_event", EventHandler(hello_handler))
    assert not event_manager.has_event_handler(EventHandler(hello_handler), "my_event")


def test_event_manager_trigger_event_unknown_event_does_not_register_it() -> None:
    event_manager = EventManager()
    event_manager.trigger_event("my_event")
    assert event_manager.events == []


def test_event_manager_trigger_event_conditional_handler() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler(
        "my_event", EventHandler(hello_handler, condition=PeriodicCondition(2))
    )
    event_manager.trigger_event("my_event")
    event_manager.trigger_event("my_event")
    event_manager.trigger_event("my_event")
    assert hello_handler.call_count == 2


def test_event_manager_has_event_handler_conditional_handler_true() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler(
        "my_event", EventHandler(hello_handler, condition=PeriodicCondition(2))
    )
    assert event_manager.has_event_handler(
        EventHandler(hello_handler, condition=PeriodicCondition(2)), "my_event"
    )


def test_event_manager_has_event_handler_conditional_handler_different_condition() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler(
        "my_event", EventHandler(hello_handler, condition=PeriodicCondition(2))
    )
    assert not event_manager.has_event_handler(
        EventHandler(hello_handler, condition=PeriodicCondition(3)), "my_event"
    )


def test_event_manager_has_event_handler_conditional_handler_without_condition() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler(
        "my_event", EventHandler(hello_handler, condition=PeriodicCondition(2))
    )
    assert not event_manager.has_event_handler(EventHandler(hello_handler), "my_event")


def test_event_manager_trigger_event_custom_condition() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler(
        "my_event", EventHandler(hello_handler, condition=CustomCondition())
    )
    event_manager.trigger_event("my_event")
    event_manager.trigger_event("my_event")
    event_manager.trigger_event("my_event")
    assert hello_handler.call_count == 2


def test_event_manager_trigger_event_custom_handler_receives_payload() -> None:
    calls: list[dict[str, Any]] = []
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", CustomHandler(calls))
    event_manager.trigger_event("my_event", value=1)
    assert calls == [{"value": 1}]


def test_event_manager_has_event_handler_custom_handler() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", CustomHandler([]))
    assert event_manager.has_event_handler(CustomHandler([]), "my_event")


def test_event_manager_trigger_event_payload_with_event_and_self_keys() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(payload_handler))
    manager.trigger_event("my_event", event="batch_end", self=1)
    assert payload_handler.kwargs == {"event": "batch_end", "self": 1}


def test_event_manager_atrigger_event_payload_with_event_and_self_keys() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(payload_handler))
    asyncio.run(manager.atrigger_event("my_event", event="batch_end", self=1))
    assert payload_handler.kwargs == {"event": "batch_end", "self": 1}


def test_event_manager_trigger_event_once_payload_with_self_key() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(payload_handler), once=True)
    manager.trigger_event("my_event", self=1)
    assert payload_handler.kwargs == {"self": 1}


def test_event_manager_atrigger_event_once_payload_with_self_key() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(payload_handler), once=True)
    asyncio.run(manager.atrigger_event("my_event", self=1))
    assert payload_handler.kwargs == {"self": 1}


def test_event_manager_trigger_event_coroutine_handler_raises() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(async_handler))
    with pytest.raises(TypeError, match=r"returned an awaitable; use ahandle or atrigger_event"):
        manager.trigger_event("my_event")


##########################################
#     Tests for user code and lock     #
##########################################


def lock_is_held(manager: EventManager) -> bool:
    r"""Indicate if the lock of the manager is held by the current
    thread."""
    acquired: list[bool] = []

    def try_acquire() -> None:
        acquired.append(manager._lock.acquire(blocking=False))
        if acquired[0]:
            manager._lock.release()

    thread = threading.Thread(target=try_acquire)
    thread.start()
    thread.join()
    return not acquired[0]


class LockProbeHandler(EventHandler):
    r"""Implements a handler that records whether the manager lock is
    held when ``equal`` or ``__repr__`` is called."""

    def __init__(self, manager: EventManager) -> None:
        super().__init__(hello_handler)
        self.manager = manager
        self.lock_held: list[bool] = []

    def __repr__(self) -> str:
        self.lock_held.append(lock_is_held(self.manager))
        return "LockProbeHandler()"

    def equal(self, other: object) -> bool:
        self.lock_held.append(lock_is_held(self.manager))
        return other is not None


def test_event_manager_remove_event_handler_equal_called_without_lock() -> None:
    manager = EventManager()
    probe = LockProbeHandler(manager)
    manager.add_event_handler("my_event", EventHandler(hello_handler))
    manager.remove_event_handler("my_event", probe)
    assert probe.lock_held == [False]


def test_event_manager_has_event_handler_equal_called_without_lock() -> None:
    manager = EventManager()
    probe = LockProbeHandler(manager)
    manager.add_event_handler("my_event", EventHandler(hello_handler))
    manager.has_event_handler(probe)
    assert probe.lock_held == [False]


def test_event_manager_repr_called_without_lock() -> None:
    manager = EventManager()
    probe = LockProbeHandler(manager)
    manager.add_event_handler("my_event", probe)
    repr(manager)
    assert probe.lock_held == [False]


def test_event_manager_remove_event_handler_removes_only_equal_registrations() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(hello_handler))
    manager.add_event_handler("my_event", EventHandler(payload_handler))
    manager.add_event_handler("my_event", EventHandler(hello_handler))
    manager.remove_event_handler("my_event", EventHandler(hello_handler))
    assert manager.has_event_handler(EventHandler(payload_handler), "my_event")
    assert not manager.has_event_handler(EventHandler(hello_handler), "my_event")


def test_event_manager_remove_event_handler_keeps_order_of_remaining_handlers() -> None:
    manager = EventManager()
    first = EventHandler(payload_handler, handler_args=(1,))
    last = EventHandler(payload_handler, handler_args=(2,))
    manager.add_event_handler("my_event", first)
    manager.add_event_handler("my_event", EventHandler(hello_handler))
    manager.add_event_handler("my_event", last)
    manager.remove_event_handler("my_event", EventHandler(hello_handler))
    assert manager._event_handlers["my_event"] == [first, last]


def test_event_manager_format_event_handlers_empty() -> None:
    assert EventManager._format_event_handlers({}) == "{}"


def test_event_manager_format_event_handlers() -> None:
    assert EventManager._format_event_handlers({"my_event": (EventHandler(print),)}).startswith(
        "\n(my_event):"
    )


def test_event_manager_trigger_event_handler_retriggering_its_event_raises_recursion_error() -> (
    None
):
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(lambda: manager.trigger_event("my_event")))
    with pytest.raises(RecursionError, match=r"maximum recursion depth exceeded"):
        manager.trigger_event("my_event")


################################################
#     Tests for get_event_handlers and len     #
################################################


def test_event_manager_len_empty() -> None:
    assert len(EventManager()) == 0


def test_event_manager_len_counts_registrations_of_all_events() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(hello_handler))
    manager.add_event_handler("my_event", EventHandler(hello_handler))
    manager.add_event_handler("my_other_event", EventHandler(hello_handler))
    assert len(manager) == 3


def test_event_manager_len_after_remove() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(hello_handler))
    subscription.remove()
    assert len(manager) == 0


def test_event_manager_get_event_handlers_empty() -> None:
    assert EventManager().get_event_handlers("my_event") == ()


def test_event_manager_get_event_handlers_does_not_create_event() -> None:
    manager = EventManager()
    manager.get_event_handlers("my_event")
    assert "my_event" not in manager


def test_event_manager_get_event_handlers_keeps_order() -> None:
    manager = EventManager()
    first = EventHandler(hello_handler)
    second = EventHandler(payload_handler)
    manager.add_event_handler("my_event", first)
    manager.add_event_handler("my_event", second)
    assert manager.get_event_handlers("my_event") == (first, second)


def test_event_manager_get_event_handlers_only_requested_event() -> None:
    manager = EventManager()
    handler = EventHandler(hello_handler)
    manager.add_event_handler("my_event", handler)
    manager.add_event_handler("my_other_event", EventHandler(payload_handler))
    assert manager.get_event_handlers("my_event") == (handler,)


def test_event_manager_get_event_handlers_unwraps_once() -> None:
    manager = EventManager()
    handler = EventHandler(hello_handler)
    manager.add_event_handler("my_event", handler, once=True)
    assert manager.get_event_handlers("my_event") == (handler,)


def test_event_manager_get_event_handlers_is_a_snapshot() -> None:
    manager = EventManager()
    handler = EventHandler(hello_handler)
    manager.add_event_handler("my_event", handler)
    handlers = manager.get_event_handlers("my_event")
    manager.add_event_handler("my_event", EventHandler(payload_handler))
    assert handlers == (handler,)


@pytest.mark.parametrize("event", INVALID_EVENTS)
def test_event_manager_get_event_handlers_event_must_be_str(event: Any) -> None:
    with pytest.raises(TypeError, match=r"event must be a str"):
        EventManager().get_event_handlers(event)


##############################################
#     Tests for subscription as a lookup     #
##############################################


def test_event_manager_has_event_handler_subscription_true() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(lambda: 1))
    assert manager.has_event_handler(subscription)


def test_event_manager_has_event_handler_subscription_with_event_true() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(lambda: 1))
    assert manager.has_event_handler(subscription, "my_event")


def test_event_manager_has_event_handler_subscription_other_event_false() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(lambda: 1))
    assert not manager.has_event_handler(subscription, "my_other_event")


def test_event_manager_has_event_handler_subscription_removed_false() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(lambda: 1))
    subscription.remove()
    assert not manager.has_event_handler(subscription)


def test_event_manager_has_event_handler_subscription_once_true() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(lambda: 1), once=True)
    assert manager.has_event_handler(subscription)


def test_event_manager_has_event_handler_subscription_equal_handler_not_matched() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(hello_handler))
    other = EventManager().add_event_handler("my_event", EventHandler(hello_handler))
    assert not manager.has_event_handler(other)


def test_event_manager_has_event_handler_subscription_incorrect_event() -> None:
    event: Any = 1
    with pytest.raises(TypeError, match=r"event must be a str"):
        EventManager().has_event_handler(
            Subscription("my_event", EventHandler(hello_handler), lambda *_: False), event
        )


def test_event_manager_remove_event_handler_subscription() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(lambda: 1))
    manager.remove_event_handler("my_event", subscription)
    assert "my_event" not in manager


def test_event_manager_remove_event_handler_subscription_keeps_equal_handlers() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(hello_handler))
    subscription = manager.add_event_handler("my_event", EventHandler(hello_handler))
    manager.remove_event_handler("my_event", subscription)
    assert len(manager) == 1


def test_event_manager_remove_event_handler_subscription_already_removed() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(lambda: 1))
    subscription.remove()
    with pytest.raises(ValueError, match=r"is not found among registered event handlers"):
        manager.remove_event_handler("my_event", subscription)


def test_event_manager_remove_event_handler_subscription_already_removed_missing_ok() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(lambda: 1))
    subscription.remove()
    manager.remove_event_handler("my_event", subscription, missing_ok=True)
    assert len(manager) == 0


def test_event_manager_remove_event_handler_subscription_other_event() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(lambda: 1))
    with pytest.raises(ValueError, match=r"is not found among registered event handlers"):
        manager.remove_event_handler("my_other_event", subscription)


def test_event_manager_remove_event_handler_subscription_other_event_keeps_registration() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(lambda: 1))
    manager.remove_event_handler("my_other_event", subscription, missing_ok=True)
    assert len(manager) == 1


def test_event_manager_remove_event_handler_subscription_of_other_manager() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(hello_handler))
    other = EventManager().add_event_handler("my_event", EventHandler(hello_handler))
    manager.remove_event_handler("my_event", other, missing_ok=True)
    assert len(manager) == 1
