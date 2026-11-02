from __future__ import annotations

import asyncio
import contextlib
import functools
import logging
import threading
from typing import Any
from unittest.mock import Mock

import pytest

from minevent import (
    BaseEventHandler,
    EventHandler,
    EventManager,
    PeriodicCondition,
    Subscription,
)
from minevent.manager import _add_error_note, _describe
from tests.unit.utils import trace

logger = logging.getLogger(__name__)

EVENTS = ("my_event", "my_other_event")


def fail() -> None:
    r"""Implements a handler that raises a ``ValueError``."""
    msg = "boom"
    raise ValueError(msg)


def add_hello_handler_when_triggered(manager: EventManager) -> None:
    r"""Register a handler that adds ``hello_handler`` to
    ``my_event``."""
    manager.add_event_handler(
        "my_event",
        EventHandler(lambda: manager.add_event_handler("my_event", EventHandler(hello_handler))),
    )


@trace
def hello_handler() -> None:
    r"""Implements a simple handler that prints hello."""
    logger.info("Hello!")


@trace
def payload_handler(*args: Any, **kwargs: Any) -> None:
    r"""Implements a handler that accepts any arguments."""
    logger.info("Payload: %s %s", args, kwargs)


##################################
#     Tests for EventManager     #
##################################


def test_event_manager_str_without_event_handler() -> None:
    assert str(EventManager()).startswith("EventManager(")


def test_event_manager_str_with_event_handler() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    assert str(event_manager).startswith("EventManager(")


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
    assert hello_handler.call_count == 1


def test_event_manager_trigger_event_2_times() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    event_manager.trigger_event("my_event")
    event_manager.trigger_event("my_event")
    assert hello_handler.call_count == 2


def test_event_manager_reset() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    event_manager.add_event_handler("my_other_event", EventHandler(hello_handler))
    event_manager.reset()
    assert len(event_manager) == 0


def test_event_manager_reset_empty() -> None:
    event_manager = EventManager()
    event_manager.reset()
    assert event_manager.events == []


def test_event_manager_trigger_event_handler_added_during_dispatch_does_not_run() -> None:
    event_manager = EventManager()
    add_hello_handler_when_triggered(event_manager)
    event_manager.trigger_event("my_event")
    assert hello_handler.call_count == 0


def test_event_manager_trigger_event_handler_added_during_dispatch_runs_next_time() -> None:
    event_manager = EventManager()
    add_hello_handler_when_triggered(event_manager)
    event_manager.trigger_event("my_event")
    event_manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


def test_event_manager_trigger_event_handler_removed_during_dispatch_still_runs() -> None:
    event_manager = EventManager()
    subscriptions: list[Subscription] = []

    def remove_hello() -> None:
        subscriptions[0].remove()

    event_manager.add_event_handler("my_event", EventHandler(remove_hello))
    subscriptions.append(event_manager.add_event_handler("my_event", EventHandler(hello_handler)))
    event_manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


def test_event_manager_trigger_event_handler_removed_during_dispatch_is_removed() -> None:
    event_manager = EventManager()
    subscriptions: list[Subscription] = []

    def remove_hello() -> None:
        subscriptions[0].remove()

    event_manager.add_event_handler("my_event", EventHandler(remove_hello))
    subscriptions.append(event_manager.add_event_handler("my_event", EventHandler(hello_handler)))
    event_manager.trigger_event("my_event")
    assert len(event_manager.get_subscriptions("my_event")) == 1


def test_event_manager_trigger_event_handler_raises() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(fail))
    with pytest.raises(ValueError, match=r"boom"):
        event_manager.trigger_event("my_event")


def test_event_manager_trigger_event_handler_raises_skips_next_handlers() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(fail))
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    with contextlib.suppress(ValueError):
        event_manager.trigger_event("my_event")
    assert hello_handler.call_count == 0


def test_event_manager_trigger_event_handler_raises_adds_note() -> None:
    event_manager = EventManager()
    handler = EventHandler(fail)
    event_manager.add_event_handler("my_event", handler)
    with pytest.raises(ValueError, match=r"boom") as exc_info:
        event_manager.trigger_event("my_event")
    assert exc_info.value.__notes__ == ["raised by fail while handling the event 'my_event'"]


def test_event_manager_trigger_event_handler_raises_same_exception_type_and_object() -> None:
    error = ValueError("boom")
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(Mock(side_effect=error)))
    with pytest.raises(ValueError, match=r"boom") as exc_info:
        event_manager.trigger_event("my_event")
    assert exc_info.value is error


def test_event_manager_trigger_event_base_exception_has_no_note() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler(
        "my_event", EventHandler(Mock(side_effect=KeyboardInterrupt("interrupted")))
    )
    with pytest.raises(KeyboardInterrupt, match=r"interrupted") as exc_info:
        event_manager.trigger_event("my_event")
    assert not hasattr(exc_info.value, "__notes__")


INVALID_EVENTS = [1, None, b"my_event"]


INVALID_EVENT_HANDLERS = [hello_handler, print, None, "handler", EventHandler]


@pytest.mark.parametrize("event_handler", INVALID_EVENT_HANDLERS)
def test_event_manager_add_event_handler_event_handler_must_be_event_handler(
    event_handler: Any,
) -> None:
    with pytest.raises(TypeError, match=r"event_handler must be a BaseEventHandler"):
        EventManager().add_event_handler("my_event", event_handler)


def test_event_manager_add_event_handler_invalid_event_handler_is_not_registered() -> None:
    manager = EventManager()
    event_handler: Any = print
    with pytest.raises(TypeError, match=r"wrap a function with EventHandler"):
        manager.add_event_handler("my_event", event_handler)
    assert "my_event" not in manager


@pytest.mark.parametrize("event", INVALID_EVENTS)
def test_event_manager_add_event_handler_event_must_be_str(event: Any) -> None:
    with pytest.raises(TypeError, match=r"event must be a str"):
        EventManager().add_event_handler(event, EventHandler(hello_handler))


@pytest.mark.parametrize("event", INVALID_EVENTS)
def test_event_manager_trigger_event_event_must_be_str(event: Any) -> None:
    with pytest.raises(TypeError, match=r"event must be a str"):
        EventManager().trigger_event(event)


def test_event_manager_repr_empty() -> None:
    assert repr(EventManager()) == "EventManager(events={})"


def test_event_manager_repr_with_event_handlers() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    event_manager.add_event_handler("my_other_event", EventHandler(hello_handler))
    assert repr(event_manager) == "EventManager(events={'my_event': 2, 'my_other_event': 1})"


def test_event_manager_events_empty() -> None:
    assert EventManager().events == []


def test_event_manager_events() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    event_manager.add_event_handler("my_other_event", EventHandler(hello_handler))
    event_manager.trigger_event("unknown_event")
    assert event_manager.events == ["my_event", "my_other_event"]


def test_event_manager_contains_false_empty() -> None:
    assert "my_event" not in EventManager()


def test_event_manager_contains_true() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    assert "my_event" in event_manager


def test_event_manager_contains_false_after_remove() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(hello_handler)).remove()
    assert "my_event" not in event_manager


def test_event_manager_clear_event() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    event_manager.add_event_handler("my_other_event", EventHandler(hello_handler))
    event_manager.clear_event("my_event")
    assert event_manager.events == ["my_other_event"]


def test_event_manager_clear_event_handlers_do_not_run() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", EventHandler(hello_handler))
    event_manager.clear_event("my_event")
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


##########################################
#     Tests for real-world scenarios     #
##########################################


class CustomCondition:
    r"""Implements a condition that is true for odd calls."""

    def __init__(self) -> None:
        self._count = 0

    def __call__(self) -> bool:
        self._count += 1
        return self._count % 2 == 1


class CustomHandler(BaseEventHandler):
    r"""Implements a handler that records the payload."""

    def __init__(self, calls: list[dict[str, Any]]) -> None:
        self._calls = calls

    def handle(self, **payload: Any) -> None:
        self._calls.append(payload)


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


########################################
#     Tests for user code and lock     #
########################################


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


def test_event_manager_trigger_event_runs_handler_without_lock() -> None:
    manager = EventManager()
    lock_held: list[bool] = []
    manager.add_event_handler(
        "my_event", EventHandler(lambda: lock_held.append(lock_is_held(manager)))
    )
    manager.trigger_event("my_event")
    assert lock_held == [False]


def test_event_manager_trigger_event_handler_retriggering_its_event_raises_recursion_error() -> (
    None
):
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(lambda: manager.trigger_event("my_event")))
    with pytest.raises(RecursionError, match=r"maximum recursion depth exceeded"):
        manager.trigger_event("my_event")


###############################################
#     Tests for get_subscriptions and len     #
###############################################


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


def test_event_manager_get_subscriptions_empty() -> None:
    assert EventManager().get_subscriptions("my_event") == ()


def test_event_manager_get_subscriptions_does_not_create_event() -> None:
    manager = EventManager()
    manager.get_subscriptions("my_event")
    assert "my_event" not in manager


def test_event_manager_get_subscriptions_keeps_order() -> None:
    manager = EventManager()
    first = manager.add_event_handler("my_event", EventHandler(hello_handler))
    second = manager.add_event_handler("my_event", EventHandler(payload_handler))
    assert manager.get_subscriptions("my_event") == (first, second)


def test_event_manager_get_subscriptions_only_requested_event() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(hello_handler))
    manager.add_event_handler("my_other_event", EventHandler(payload_handler))
    assert manager.get_subscriptions("my_event") == (subscription,)


def test_event_manager_get_subscriptions_is_a_snapshot() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(hello_handler))
    subscriptions = manager.get_subscriptions("my_event")
    manager.add_event_handler("my_event", EventHandler(payload_handler))
    assert subscriptions == (subscription,)


@pytest.mark.parametrize("event", INVALID_EVENTS)
def test_event_manager_get_subscriptions_event_must_be_str(event: Any) -> None:
    with pytest.raises(TypeError, match=r"event must be a str"):
        EventManager().get_subscriptions(event)


##############################################
#     Tests for subscription as a lookup     #
##############################################


###############################################
#     Tests for subscription conveniences     #
###############################################


def test_event_manager_subscription_active_after_add() -> None:
    manager = EventManager()
    assert manager.add_event_handler("my_event", EventHandler(hello_handler)).active


def test_event_manager_subscription_active_after_remove() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(hello_handler))
    subscription.remove()
    assert not subscription.active


def test_event_manager_subscription_active_after_reset() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(hello_handler))
    manager.reset()
    assert not subscription.active


def test_event_manager_subscription_active_after_once_ran() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(hello_handler), once=True)
    manager.trigger_event("my_event")
    assert not subscription.active


def test_event_manager_subscription_active_other_equal_handler_removed() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(hello_handler))
    other = manager.add_event_handler("my_event", EventHandler(hello_handler))
    other.remove()
    assert subscription.active


def test_event_manager_subscription_context_manager_removes_on_exit() -> None:
    manager = EventManager()
    with manager.add_event_handler("my_event", EventHandler(hello_handler)):
        manager.trigger_event("my_event")
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


def test_event_manager_on_registers_function() -> None:
    manager = EventManager()

    @manager.on("my_event")
    def handler() -> None:
        hello_handler()

    manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


def test_event_manager_on_returns_function_unchanged() -> None:
    manager = EventManager()

    def handler() -> None:
        pass

    assert manager.on("my_event")(handler) is handler


def test_event_manager_on_passes_payload() -> None:
    manager = EventManager()
    manager.on("my_event")(payload_handler)
    manager.trigger_event("my_event", epoch=3)
    assert payload_handler.kwargs == {"epoch": 3}


def test_event_manager_on_once() -> None:
    manager = EventManager()
    manager.on("my_event", once=True)(hello_handler)
    manager.trigger_event("my_event")
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


def test_event_manager_on_event_registered() -> None:
    manager = EventManager()
    manager.on("my_event")(hello_handler)
    assert manager.events == ["my_event"]


@pytest.mark.parametrize("event", INVALID_EVENTS)
def test_event_manager_on_event_must_be_str(event: Any) -> None:
    with pytest.raises(TypeError, match=r"event must be a str"):
        EventManager().on(event)


def test_event_manager_trigger_event_filter_payload_shares_event() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(hello_handler, filter_payload=True))
    manager.add_event_handler("my_event", EventHandler(payload_handler))
    manager.trigger_event("my_event", epoch=3, loss=0.5)
    assert payload_handler.kwargs == {"epoch": 3, "loss": 0.5}


def test_event_manager_trigger_event_filter_payload_does_not_fail_other_handler() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(hello_handler, filter_payload=True))
    manager.trigger_event("my_event", epoch=3)
    assert hello_handler.call_count == 1


def test_event_manager_get_subscriptions_event_handler() -> None:
    manager = EventManager()
    handler = EventHandler(hello_handler)
    manager.add_event_handler("my_event", handler, once=True)
    assert manager.get_subscriptions("my_event")[0].event_handler is handler


def fail_with_arguments(*args: object) -> None:
    r"""Implements a handler with arguments that raises a ``ValueError``."""
    msg = f"boom {len(args)}"
    raise ValueError(msg)


def test_event_manager_trigger_event_note_ignores_repr_of_arguments() -> None:
    class BadRepr:
        def __repr__(self) -> str:
            msg = "repr failed"
            raise RuntimeError(msg)

    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(fail_with_arguments, [BadRepr()]))
    with pytest.raises(ValueError, match=r"boom"):
        manager.trigger_event("my_event")


def test_event_manager_trigger_event_note_is_short_for_large_arguments() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(fail_with_arguments, [list(range(10_000))]))
    with pytest.raises(ValueError, match=r"boom") as exc_info:
        manager.trigger_event("my_event")
    assert len(exc_info.value.__notes__[0]) < 100


###############################
#     Tests for _describe     #
###############################


class CallableObject:
    def __call__(self) -> None:
        r"""Implement a callable without a name."""


class CustomEventHandler(BaseEventHandler):
    def handle(self, /, **payload: object) -> None:
        r"""Implement a custom event handler."""


def test_describe_function() -> None:
    assert _describe(EventHandler(fail)) == "fail"


def test_describe_method() -> None:
    assert _describe(EventHandler(CustomEventHandler().handle)) == "CustomEventHandler.handle"


def test_describe_partial() -> None:
    assert _describe(EventHandler(functools.partial(fail))) == "partial"


def test_describe_callable_object() -> None:
    assert _describe(EventHandler(CallableObject())) == "CallableObject"


def test_describe_custom_event_handler() -> None:
    assert _describe(CustomEventHandler()) == "CustomEventHandler"


#####################################
#     Tests for _add_error_note     #
#####################################


def test_add_error_note() -> None:
    error = ValueError("boom")
    _add_error_note(error, "my_event", EventHandler(fail))
    assert error.__notes__ == ["raised by fail while handling the event 'my_event'"]


def failing_handler() -> None:
    msg = "handler failed"
    raise RuntimeError(msg)


##################################
#     Tests for Subscription     #
##################################


def test_subscription_repr() -> None:
    assert repr(Subscription(EventManager(), "my_event", EventHandler(print))) == (
        "Subscription(event='my_event')"
    )


def test_subscription_event() -> None:
    assert Subscription(EventManager(), "my_event", EventHandler(print)).event == "my_event"


def test_subscription_event_handler() -> None:
    handler = EventHandler(print)
    assert Subscription(EventManager(), "my_event", handler).event_handler is handler


def test_subscription_once_default() -> None:
    assert not Subscription(EventManager(), "my_event", EventHandler(print)).once


def test_subscription_once_true() -> None:
    assert Subscription(EventManager(), "my_event", EventHandler(print), once=True).once


def test_subscription_active_after_add() -> None:
    assert EventManager().add_event_handler("my_event", EventHandler(print)).active


def test_subscription_remove_returns_true() -> None:
    assert EventManager().add_event_handler("my_event", EventHandler(print)).remove()


def test_subscription_remove_twice_returns_false() -> None:
    subscription = EventManager().add_event_handler("my_event", EventHandler(print))
    subscription.remove()
    assert not subscription.remove()


def test_subscription_remove_inactive_after_remove() -> None:
    subscription = EventManager().add_event_handler("my_event", EventHandler(print))
    subscription.remove()
    assert not subscription.active


def test_subscription_remove_removes_from_manager() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(print)).remove()
    assert len(manager) == 0


def test_subscription_remove_same_handler_registered_twice_keeps_other_registration() -> None:
    manager = EventManager()
    handler = EventHandler(print)
    first = manager.add_event_handler("my_event", handler)
    manager.add_event_handler("my_event", handler)
    first.remove()
    first.remove()
    assert len(manager) == 1


def test_subscription_remove_same_handler_registered_twice_second_stays_active() -> None:
    manager = EventManager()
    handler = EventHandler(print)
    first = manager.add_event_handler("my_event", handler)
    second = manager.add_event_handler("my_event", handler)
    first.remove()
    first.remove()
    assert second.active


def test_subscription_inactive_after_clear_event() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(print))
    manager.clear_event("my_event")
    assert not subscription.active


def test_subscription_remove_after_clear_event_returns_false() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(print))
    manager.clear_event("my_event")
    assert not subscription.remove()


def test_subscription_inactive_after_reset() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(print))
    manager.reset()
    assert not subscription.active


def test_subscription_enter_returns_subscription() -> None:
    subscription = EventManager().add_event_handler("my_event", EventHandler(print))
    with subscription as entered:
        assert entered is subscription


def test_subscription_exit_removes() -> None:
    manager = EventManager()
    with manager.add_event_handler("my_event", EventHandler(print)):
        pass
    assert len(manager) == 0


def test_subscription_exit_removes_when_block_raises() -> None:
    manager = EventManager()
    with (
        pytest.raises(RuntimeError, match=r"handler failed"),
        manager.add_event_handler("my_event", EventHandler(print)),
    ):
        failing_handler()
    assert len(manager) == 0
