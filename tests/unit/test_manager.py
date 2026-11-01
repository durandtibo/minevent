from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import pytest

from minevent import EventHandler, EventManager, Subscription
from minevent.manager import _OnceEventHandler, _unwrap
from tests.unit.utils import trace

if TYPE_CHECKING:
    from collections.abc import Callable

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
    def reset_func(func: Callable) -> None:
        func.called = False
        func.call_count = 0
        func.args = ()
        func.kwargs = {}

    reset_func(hello_handler)
    reset_func(payload_handler)
    reset_func(failing_handler)


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
def test_event_manager_add_event_handler_event_must_be_str(event: object) -> None:
    with pytest.raises(TypeError, match=r"event must be a str"):
        EventManager().add_event_handler(event, EventHandler(hello_handler))


@pytest.mark.parametrize("event", INVALID_EVENTS)
def test_event_manager_trigger_event_event_must_be_str(event: object) -> None:
    with pytest.raises(TypeError, match=r"event must be a str"):
        EventManager().trigger_event(event)


@pytest.mark.parametrize("event", INVALID_EVENTS)
def test_event_manager_remove_event_handler_event_must_be_str(event: object) -> None:
    with pytest.raises(TypeError, match=r"event must be a str"):
        EventManager().remove_event_handler(event, EventHandler(hello_handler))


def test_event_manager_has_event_handler_event_must_be_str() -> None:
    with pytest.raises(TypeError, match=r"event must be a str"):
        EventManager().has_event_handler(EventHandler(hello_handler), event=1)


def test_event_manager_remove_event_handler_missing_ok() -> None:
    event_manager = EventManager()
    event_manager.remove_event_handler("my_event", EventHandler(hello_handler), missing_ok=True)
    event_manager.add_event_handler("my_event", EventHandler(lambda: True))
    event_manager.remove_event_handler("my_event", EventHandler(hello_handler), missing_ok=True)
    assert event_manager.has_event_handler(EventHandler(lambda: True), "my_event") is False
    event_manager.trigger_event("my_event")


def test_event_manager_repr_empty() -> None:
    assert repr(EventManager()) == (
        "EventManager(\n  (event_handlers): \n  (last_triggered_event): None\n)"
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
    with pytest.raises(TypeError, match=r"event must be a str"):
        EventManager().clear_event(1)


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
