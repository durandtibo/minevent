from __future__ import annotations

import copy
import functools
import inspect
import logging
import pickle
import threading
from collections.abc import Awaitable
from types import MappingProxyType
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock

import pytest

from minevent import (
    Context,
    EventManager,
    PeriodicCondition,
    Subscription,
)
from minevent.manager import (
    _add_error_note,
    _as_context,
    _check_event,
    _check_not_awaitable,
    _describe,
    _needs_context,
)
from tests.unit.utils import raised, trace

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

EVENTS = ("my_event", "my_other_event")


def fail() -> None:
    r"""Implements a handler that raises a ``ValueError``."""
    msg = "boom"
    raise ValueError(msg)


def read_epoch(context: Context) -> object:
    r"""Implement a handler that reads the required key ``epoch``."""
    return context["epoch"]


def has_payload(context: Context) -> bool:
    r"""Implement a condition that is ``True`` if the context is not
    empty."""
    return bool(context)


def copy_context(context: Context) -> dict[str, object]:
    r"""Implement a handler that returns a copy of the context."""
    return dict(context)


def registered_subscription(manager: EventManager) -> Subscription:
    r"""Return the first ``Subscription`` registered to ``my_event``."""
    return manager.get_subscriptions("my_event")[0]


def add_hello_handler_when_triggered(manager: EventManager) -> None:
    r"""Register a handler that adds ``hello_handler`` to
    ``my_event``."""
    manager.add_event_handler(
        "my_event", lambda: manager.add_event_handler("my_event", hello_handler)
    )


class BadReprCallable:
    r"""Implement a handler whose ``repr`` raises."""

    def __repr__(self) -> str:
        msg = "repr failed"
        raise RuntimeError(msg)

    def __call__(self) -> None:
        r"""Implement a handler."""


async def async_handler_with_argument(secret: str) -> None:
    r"""Implement a coroutine handler that has an argument."""


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
    event_manager.add_event_handler("my_event", hello_handler)
    assert str(event_manager).startswith("EventManager(")


@pytest.mark.parametrize("event", EVENTS)
def test_event_manager_add_event_handler_event(event: str) -> None:
    event_manager = EventManager()
    event_manager.add_event_handler(event, hello_handler)
    event_manager.trigger_event(event)
    assert hello_handler.call_count == 1


def test_event_manager_add_event_handler_duplicate_event_handlers() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", hello_handler)
    event_manager.add_event_handler("my_event", hello_handler)
    event_manager.trigger_event("my_event")
    assert hello_handler.call_count == 2


@pytest.mark.parametrize("event", EVENTS)
def test_event_manager_trigger_event(event: str) -> None:
    event_manager = EventManager()
    event_manager.add_event_handler(event, hello_handler)
    event_manager.trigger_event(event)
    assert hello_handler.call_count == 1


def test_event_manager_trigger_event_2_times() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", hello_handler)
    event_manager.trigger_event("my_event")
    event_manager.trigger_event("my_event")
    assert hello_handler.call_count == 2


def test_event_manager_reset() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", hello_handler)
    event_manager.add_event_handler("my_other_event", hello_handler)
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


def test_event_manager_trigger_event_removed_registration_does_not_run() -> None:
    event_manager = EventManager()
    subscriptions: list[Subscription] = []

    def remove_hello() -> None:
        subscriptions[0].remove()

    event_manager.add_event_handler("my_event", remove_hello)
    subscriptions.append(event_manager.add_event_handler("my_event", hello_handler))
    event_manager.trigger_event("my_event")
    assert hello_handler.call_count == 0


def test_event_manager_trigger_event_removed_by_clear_event_does_not_run() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", lambda: event_manager.clear_event("my_event"))
    event_manager.add_event_handler("my_event", hello_handler)
    event_manager.trigger_event("my_event")
    assert hello_handler.call_count == 0


def test_event_manager_trigger_event_removed_by_reset_does_not_run() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", event_manager.reset)
    event_manager.add_event_handler("my_event", hello_handler)
    event_manager.trigger_event("my_event")
    assert hello_handler.call_count == 0


def test_event_manager_trigger_event_removed_by_clear_event_keeps_other_events() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", lambda: event_manager.clear_event("other_event"))
    event_manager.add_event_handler("my_event", hello_handler)
    event_manager.add_event_handler("other_event", print)
    event_manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


def test_event_manager_trigger_event_handler_removed_during_dispatch_is_removed() -> None:
    event_manager = EventManager()
    subscriptions: list[Subscription] = []

    def remove_hello() -> None:
        subscriptions[0].remove()

    event_manager.add_event_handler("my_event", remove_hello)
    subscriptions.append(event_manager.add_event_handler("my_event", hello_handler))
    event_manager.trigger_event("my_event")
    assert len(event_manager.get_subscriptions("my_event")) == 1


def test_event_manager_trigger_event_handler_raises() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", fail)
    with pytest.raises(ValueError, match=r"boom"):
        event_manager.trigger_event("my_event")


def test_event_manager_trigger_event_handler_raises_skips_next_handlers() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", fail)
    event_manager.add_event_handler("my_event", hello_handler)
    with pytest.raises(ValueError, match=r"boom"):
        event_manager.trigger_event("my_event")
    assert hello_handler.call_count == 0


def test_event_manager_trigger_event_handler_raises_adds_note() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", fail)
    error = raised(event_manager.trigger_event, "my_event")
    assert error.__notes__ == ["raised by fail while handling the event 'my_event'"]


def test_event_manager_trigger_event_reused_exception_has_one_note() -> None:
    error = ValueError("boom")
    manager = EventManager()
    manager.add_event_handler("my_event", Mock(side_effect=error, __qualname__="f"))
    raised(manager.trigger_event, "my_event")
    raised(manager.trigger_event, "my_event")
    raised(manager.trigger_event, "my_event")
    assert len(error.__notes__) == 1


def test_event_manager_trigger_event_retrigger_own_event_has_one_note() -> None:
    manager = EventManager()

    def retrigger() -> None:
        manager.trigger_event("my_event")

    manager.add_event_handler("my_event", retrigger)
    assert raised(manager.trigger_event, "my_event").__notes__ == [
        f"raised by {retrigger.__qualname__} while handling the event 'my_event'"
    ]


def test_event_manager_trigger_event_nested_events_have_one_note_each() -> None:
    manager = EventManager()

    def trigger_b() -> None:
        manager.trigger_event("b")

    manager.add_event_handler("a", trigger_b)
    manager.add_event_handler("b", fail)
    assert raised(manager.trigger_event, "a").__notes__ == [
        "raised by fail while handling the event 'b'",
        f"raised by {trigger_b.__qualname__} while handling the event 'a'",
    ]


def test_event_manager_trigger_event_handler_raises_same_exception_type_and_object() -> None:
    error = ValueError("boom")
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", Mock(side_effect=error))
    assert raised(event_manager.trigger_event, "my_event") is error


def test_event_manager_trigger_event_base_exception_has_no_note() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", Mock(side_effect=KeyboardInterrupt("interrupted")))
    assert not hasattr(raised(event_manager.trigger_event, "my_event"), "__notes__")


INVALID_EVENTS = [1, None, b"my_event"]


INVALID_HANDLERS = [None, "handler", 5, EventManager()]


@pytest.mark.parametrize("handler", INVALID_HANDLERS)
def test_event_manager_add_event_handler_handler_must_be_callable(handler: Any) -> None:
    with pytest.raises(TypeError, match=r"handler must be callable"):
        EventManager().add_event_handler("my_event", handler)


@pytest.mark.parametrize("handler", INVALID_HANDLERS)
def test_event_manager_add_event_handler_invalid_handler_is_not_registered(handler: Any) -> None:
    manager = EventManager()
    with pytest.raises(TypeError, match=r"handler must be callable"):
        manager.add_event_handler("my_event", handler)
    assert len(manager) == 0


@pytest.mark.parametrize("handler", INVALID_HANDLERS)
def test_event_manager_on_handler_must_be_callable(handler: Any) -> None:
    with pytest.raises(TypeError, match=r"handler must be callable"):
        EventManager().on("my_event")(handler)


def test_event_manager_on_invalid_handler_is_not_registered() -> None:
    manager = EventManager()
    handler: Any = 5
    with pytest.raises(TypeError, match=r"handler must be callable"):
        manager.on("my_event")(handler)
    assert len(manager) == 0


def test_event_manager_add_event_handler_condition_must_be_callable() -> None:
    condition: Any = 5
    with pytest.raises(TypeError, match=r"condition must be callable"):
        EventManager().add_event_handler("my_event", hello_handler, condition=condition)


def test_event_manager_add_event_handler_invalid_condition_is_not_registered() -> None:
    manager = EventManager()
    condition: Any = 5
    with pytest.raises(TypeError, match=r"condition must be callable"):
        manager.add_event_handler("my_event", hello_handler, condition=condition)
    assert len(manager) == 0


def test_event_manager_add_event_handler_plain_function() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler)
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


def test_event_manager_add_event_handler_callable_object() -> None:
    manager = EventManager()
    calls: list[dict[str, Any]] = []
    manager.add_event_handler("my_event", CallableRecorder(calls))
    manager.trigger_event("my_event", {"epoch": 3})
    assert calls == [{"epoch": 3}]


def test_event_manager_add_event_handler_event_handler_still_accepted() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler)
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


def test_event_manager_add_event_handler_partial_binds_positional_argument() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", functools.partial(payload_handler, 1, 2))
    manager.trigger_event("my_event", {"epoch": 3})
    assert payload_handler.args == (1, 2, {"epoch": 3})


def test_event_manager_add_event_handler_partial_binds_keyword_argument() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", functools.partial(payload_handler, k=1))
    manager.trigger_event("my_event", {"epoch": 3})
    assert (payload_handler.args, payload_handler.kwargs) == (({"epoch": 3},), {"k": 1})


def test_event_manager_add_event_handler_payload_does_not_override_keyword_bound_by_partial() -> (
    None
):
    manager = EventManager()
    manager.add_event_handler("my_event", functools.partial(payload_handler, k=1))
    manager.trigger_event("my_event", {"k": 2})
    assert (payload_handler.args, payload_handler.kwargs) == (({"k": 2},), {"k": 1})


def test_event_manager_add_event_handler_condition_false_does_not_run_handler() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler, condition=lambda: False)
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 0


def test_event_manager_add_event_handler_condition_true_runs_handler() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler, condition=lambda: True)
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


def test_event_manager_add_event_handler_condition_default_is_none() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler)
    assert registered_subscription(manager).condition is None


def test_event_manager_add_event_handler_options_reach_subscription() -> None:
    manager = EventManager()
    condition = PeriodicCondition(freq=2)
    subscription = manager.add_event_handler(
        "my_event", hello_handler, once=True, condition=condition
    )
    assert {
        "event": subscription.event,
        "handler": subscription.handler,
        "once": subscription.once,
        "condition": subscription.condition,
    } == {
        "event": "my_event",
        "handler": hello_handler,
        "once": True,
        "condition": condition,
    }


def test_event_manager_on_and_add_event_handler_give_same_options() -> None:
    manager = EventManager()
    condition = PeriodicCondition(freq=2)
    manager.on("my_event", once=True, condition=condition)(hello_handler)
    subscription = manager.add_event_handler(
        "my_event", hello_handler, once=True, condition=condition
    )
    first = registered_subscription(manager)
    assert (first.handler, first.once, first.condition) == (
        subscription.handler,
        subscription.once,
        subscription.condition,
    )


@pytest.mark.parametrize("event", INVALID_EVENTS)
def test_event_manager_add_event_handler_event_must_be_str(event: Any) -> None:
    with pytest.raises(TypeError, match=r"event must be a str"):
        EventManager().add_event_handler(event, hello_handler)


@pytest.mark.parametrize("event", INVALID_EVENTS)
def test_event_manager_trigger_event_event_must_be_str(event: Any) -> None:
    with pytest.raises(TypeError, match=r"event must be a str"):
        EventManager().trigger_event(event)


def test_event_manager_repr_empty() -> None:
    assert repr(EventManager()) == "EventManager(events={})"


def test_event_manager_repr_with_event_handlers() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", hello_handler)
    event_manager.add_event_handler("my_event", hello_handler)
    event_manager.add_event_handler("my_other_event", hello_handler)
    assert repr(event_manager) == "EventManager(events={'my_event': 2, 'my_other_event': 1})"


def test_event_manager_events_empty() -> None:
    assert EventManager().events == []


def test_event_manager_events() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", hello_handler)
    event_manager.add_event_handler("my_other_event", hello_handler)
    event_manager.trigger_event("unknown_event")
    assert event_manager.events == ["my_event", "my_other_event"]


def test_event_manager_contains_false_empty() -> None:
    assert "my_event" not in EventManager()


def test_event_manager_contains_true() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", hello_handler)
    assert "my_event" in event_manager


def test_event_manager_contains_false_after_remove() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", hello_handler).remove()
    assert "my_event" not in event_manager


def test_event_manager_clear_event() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", hello_handler)
    event_manager.add_event_handler("my_event", hello_handler)
    event_manager.add_event_handler("my_other_event", hello_handler)
    event_manager.clear_event("my_event")
    assert event_manager.events == ["my_other_event"]


def test_event_manager_clear_event_handlers_do_not_run() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", hello_handler)
    event_manager.clear_event("my_event")
    event_manager.trigger_event("my_event")
    assert hello_handler.call_count == 0


def test_event_manager_clear_event_missing() -> None:
    manager = EventManager()
    manager.clear_event("my_event")
    assert manager.events == []


def test_event_manager_clear_event_must_be_str() -> None:
    event: Any = 1
    with pytest.raises(TypeError, match=r"event must be a str"):
        EventManager().clear_event(event)


###########################################
#     Tests for trigger_event payload     #
###########################################


def test_event_manager_trigger_event_payload() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler)
    manager.trigger_event("my_event", {"epoch": 3, "loss": 0.5})
    assert payload_handler.args == ({"epoch": 3, "loss": 0.5},)


def test_event_manager_trigger_event_payload_all_handlers() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler)
    manager.add_event_handler("my_event", functools.partial(payload_handler, 1))
    manager.trigger_event("my_event", {"epoch": 3})
    assert payload_handler.call_count == 2


def test_event_manager_trigger_event_without_payload() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler)
    manager.trigger_event("my_event")
    assert payload_handler.args == ({},)


def test_event_manager_trigger_event_payload_is_a_context() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler)
    manager.trigger_event("my_event", {"epoch": 3})
    assert isinstance(payload_handler.args[0], Context)


def test_event_manager_trigger_event_payload_ignored_by_handler_without_parameter() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler)
    manager.trigger_event("my_event", {"epoch": 3})
    assert hello_handler.call_count == 1


def test_event_manager_trigger_event_handler_without_parameter_called_without_argument() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler)
    manager.trigger_event("my_event", {"epoch": 3})
    assert (hello_handler.args, hello_handler.kwargs) == ((), {})


def test_event_manager_trigger_event_handlers_read_different_keys() -> None:
    manager = EventManager()
    calls: list[object] = []
    manager.add_event_handler("my_event", lambda context: calls.append(context["epoch"]))
    manager.add_event_handler("my_event", lambda context: calls.append(context["loss"]))
    manager.trigger_event("my_event", {"epoch": 3, "loss": 0.5})
    assert calls == [3, 0.5]


def test_event_manager_trigger_event_handler_missing_key_raises_key_error() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", read_epoch)
    with pytest.raises(KeyError, match=r"key 'epoch' not found in the context") as exc_info:
        manager.trigger_event("my_event", {"loss": 0.5})
    assert exc_info.value.__notes__ == ["raised by read_epoch while handling the event 'my_event'"]


def test_event_manager_trigger_event_handler_missing_key_with_default() -> None:
    manager = EventManager()
    calls: list[object] = []
    manager.add_event_handler("my_event", lambda context: calls.append(context.get("epoch", -1)))
    manager.trigger_event("my_event", {"loss": 0.5})
    assert calls == [-1]


def test_event_manager_trigger_event_all_handlers_share_one_context() -> None:
    manager = EventManager()
    contexts: list[Context] = []
    manager.add_event_handler("my_event", contexts.append)
    manager.add_event_handler("my_event", contexts.append)
    manager.trigger_event("my_event", {"epoch": 3})
    assert contexts[0] is contexts[1]


def test_event_manager_trigger_event_new_context_for_each_trigger() -> None:
    manager = EventManager()
    contexts: list[Context] = []
    manager.add_event_handler("my_event", contexts.append)
    manager.trigger_event("my_event", {"epoch": 1})
    manager.trigger_event("my_event", {"epoch": 2})
    assert contexts == [{"epoch": 1}, {"epoch": 2}]


def test_event_manager_trigger_event_context_is_read_only() -> None:
    manager = EventManager()

    def handler(context: Any) -> None:
        context["epoch"] = 0

    manager.add_event_handler("my_event", handler)
    with pytest.raises(TypeError, match=r"does not support item assignment"):
        manager.trigger_event("my_event", {"epoch": 3})


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


class CallableRecorder:
    r"""Implements a callable object that records the payload."""

    def __init__(self, calls: list[dict[str, Any]]) -> None:
        self._calls = calls

    def __call__(self, context: Context) -> None:
        self._calls.append(dict(context))


def test_event_manager_trigger_event_unknown_event_does_not_register_it() -> None:
    event_manager = EventManager()
    event_manager.trigger_event("my_event")
    assert event_manager.events == []


def test_event_manager_trigger_event_conditional_handler() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", hello_handler, condition=PeriodicCondition(2))
    event_manager.trigger_event("my_event")
    event_manager.trigger_event("my_event")
    event_manager.trigger_event("my_event")
    assert hello_handler.call_count == 2


def test_event_manager_trigger_event_custom_condition() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", hello_handler, condition=CustomCondition())
    event_manager.trigger_event("my_event")
    event_manager.trigger_event("my_event")
    event_manager.trigger_event("my_event")
    assert hello_handler.call_count == 2


def test_event_manager_trigger_event_custom_handler_receives_payload() -> None:
    calls: list[dict[str, Any]] = []
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", CallableRecorder(calls))
    event_manager.trigger_event("my_event", {"value": 1})
    assert calls == [{"value": 1}]


def test_event_manager_trigger_event_payload_with_event_and_self_keys() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler)
    manager.trigger_event("my_event", {"event": "batch_end", "self": 1})
    assert payload_handler.args == ({"event": "batch_end", "self": 1},)


async def test_event_manager_atrigger_event_payload_with_event_and_self_keys() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler)
    await manager.atrigger_event("my_event", {"event": "batch_end", "self": 1})
    assert payload_handler.args == ({"event": "batch_end", "self": 1},)


def test_event_manager_trigger_event_once_payload_with_self_key() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler, once=True)
    manager.trigger_event("my_event", {"self": 1})
    assert payload_handler.args == ({"self": 1},)


async def test_event_manager_atrigger_event_once_payload_with_self_key() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler, once=True)
    await manager.atrigger_event("my_event", {"self": 1})
    assert payload_handler.args == ({"self": 1},)


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
    manager.add_event_handler("my_event", lambda: lock_held.append(lock_is_held(manager)))
    manager.trigger_event("my_event")
    assert lock_held == [False]


def test_event_manager_trigger_event_handler_retriggering_its_event_raises_recursion_error() -> (
    None
):
    manager = EventManager()
    manager.add_event_handler("my_event", lambda: manager.trigger_event("my_event"))
    with pytest.raises(RecursionError, match=r"maximum recursion depth exceeded"):
        manager.trigger_event("my_event")


#################################################
#     Tests for truthiness, copy and pickle     #
#################################################


def test_event_manager_bool_empty() -> None:
    assert bool(EventManager()) is True


def test_event_manager_bool_with_registration() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler)
    assert bool(manager) is True


def test_event_manager_empty_manager_or_default_keeps_manager() -> None:
    manager = EventManager()
    assert (manager or EventManager()) is manager


@pytest.mark.parametrize("func", [copy.copy, copy.deepcopy, pickle.dumps])
def test_event_manager_copy_and_pickle_raise_type_error(func: Callable[[object], object]) -> None:
    with pytest.raises(TypeError, match=r"EventManager cannot be copied or pickled"):
        func(EventManager())


def test_event_manager_copy_subclass_names_subclass() -> None:
    class MyManager(EventManager):
        pass

    with pytest.raises(TypeError, match=r"MyManager cannot be copied or pickled"):
        copy.copy(MyManager())


###############################################
#     Tests for get_subscriptions and len     #
###############################################


def test_event_manager_len_empty() -> None:
    assert len(EventManager()) == 0


def test_event_manager_len_counts_registrations_of_all_events() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler)
    manager.add_event_handler("my_event", hello_handler)
    manager.add_event_handler("my_other_event", hello_handler)
    assert len(manager) == 3


def test_event_manager_len_after_remove() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", hello_handler)
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
    first = manager.add_event_handler("my_event", hello_handler)
    second = manager.add_event_handler("my_event", payload_handler)
    assert manager.get_subscriptions("my_event") == (first, second)


def test_event_manager_get_subscriptions_only_requested_event() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", hello_handler)
    manager.add_event_handler("my_other_event", payload_handler)
    assert manager.get_subscriptions("my_event") == (subscription,)


def test_event_manager_get_subscriptions_is_a_snapshot() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", hello_handler)
    subscriptions = manager.get_subscriptions("my_event")
    manager.add_event_handler("my_event", payload_handler)
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


def test_event_manager_subscription_active_after_once_ran() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", hello_handler, once=True)
    manager.trigger_event("my_event")
    assert not subscription.active


def test_event_manager_subscription_context_manager_removes_on_exit() -> None:
    manager = EventManager()
    with manager.add_event_handler("my_event", hello_handler):
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
    manager.trigger_event("my_event", {"epoch": 3})
    assert payload_handler.args == ({"epoch": 3},)


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


def test_event_manager_on_condition_reaches_subscription() -> None:
    manager = EventManager()
    manager.on("my_event", condition=PeriodicCondition(freq=2))(hello_handler)
    assert isinstance(registered_subscription(manager).condition, PeriodicCondition)


def test_event_manager_on_condition_false_does_not_run_handler() -> None:
    manager = EventManager()
    manager.on("my_event", condition=lambda: False)(hello_handler)
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 0


def test_event_manager_on_condition_true_runs_handler() -> None:
    manager = EventManager()
    manager.on("my_event", condition=lambda: True)(hello_handler)
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


def test_event_manager_on_condition_evaluated_before_handler() -> None:
    manager = EventManager()
    calls: list[str] = []

    def condition() -> bool:
        calls.append("condition")
        return True

    @manager.on("my_event", condition=condition)
    def handler() -> None:
        calls.append("handler")

    manager.trigger_event("my_event")
    assert calls == ["condition", "handler"]


def test_event_manager_trigger_event_condition_reads_the_payload() -> None:
    manager = EventManager()
    manager.add_event_handler(
        "my_event", hello_handler, condition=lambda context: context.get("epoch", 0) >= 2
    )
    for epoch in range(4):
        manager.trigger_event("my_event", {"epoch": epoch})
    assert hello_handler.call_count == 2


def test_event_manager_on_condition_reads_the_payload() -> None:
    manager = EventManager()
    manager.on("my_event", condition=lambda context: context["go"])(hello_handler)
    manager.trigger_event("my_event", {"go": True})
    manager.trigger_event("my_event", {"go": False})
    assert hello_handler.call_count == 1


def test_event_manager_trigger_event_condition_with_parameter_and_handler_without() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler, condition=has_payload)
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 0


def test_event_manager_on_condition_returns_function_unchanged() -> None:
    manager = EventManager()
    assert manager.on("my_event", condition=lambda: True)(hello_handler) is hello_handler


def test_event_manager_on_once_with_options() -> None:
    manager = EventManager()
    manager.on("my_event", once=True, condition=lambda: True)(hello_handler)
    manager.trigger_event("my_event")
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


def test_event_manager_on_condition_not_callable() -> None:
    condition: Any = 1
    with pytest.raises(TypeError, match=r"condition must be callable"):
        EventManager().on("my_event", condition=condition)(hello_handler)


@pytest.mark.parametrize("event", INVALID_EVENTS)
def test_event_manager_on_event_must_be_str(event: Any) -> None:
    with pytest.raises(TypeError, match=r"event must be a str"):
        EventManager().on(event)


def test_event_manager_get_subscriptions_event_handler() -> None:
    manager = EventManager()
    handler = hello_handler
    manager.add_event_handler("my_event", handler, once=True)
    assert manager.get_subscriptions("my_event")[0].handler is handler


def fail_with_arguments(*args: object) -> None:
    r"""Implements a handler with arguments that raises a
    ``ValueError``."""
    msg = f"boom {len(args)}"
    raise ValueError(msg)


def test_event_manager_trigger_event_note_ignores_repr_of_arguments() -> None:
    class BadRepr:
        def __repr__(self) -> str:
            msg = "repr failed"
            raise RuntimeError(msg)

    manager = EventManager()
    manager.add_event_handler("my_event", functools.partial(fail_with_arguments, BadRepr()))
    with pytest.raises(ValueError, match=r"boom"):
        manager.trigger_event("my_event")


def test_event_manager_trigger_event_note_is_short_for_large_arguments() -> None:
    manager = EventManager()
    manager.add_event_handler(
        "my_event", functools.partial(fail_with_arguments, list(range(10_000)))
    )
    assert len(raised(manager.trigger_event, "my_event").__notes__[0]) < 100


###############################
#     Tests for _describe     #
###############################


class CallableObject:
    def __call__(self) -> None:
        r"""Implement a callable without a name."""


def test_describe_function() -> None:
    assert _describe(fail) == "fail"


def test_describe_partial() -> None:
    assert _describe(functools.partial(fail)) == "fail"


def test_describe_partial_with_arguments() -> None:
    assert _describe(functools.partial(payload_handler, 1, k=2)) == "payload_handler"


def test_describe_nested_partial() -> None:
    assert _describe(functools.partial(functools.partial(fail))) == "fail"


def test_describe_method() -> None:
    assert _describe(CallableObject().__call__) == "CallableObject.__call__"


def test_describe_callable_object() -> None:
    assert _describe(CallableObject()) == "CallableObject"


#####################################
#     Tests for _add_error_note     #
#####################################


def test_add_error_note() -> None:
    error = ValueError("boom")
    _add_error_note(error, "my_event", fail)
    assert error.__notes__ == ["raised by fail while handling the event 'my_event'"]


def test_add_error_note_same_pair_twice_adds_one_note() -> None:
    error = ValueError("boom")
    handler = fail
    _add_error_note(error, "my_event", handler)
    _add_error_note(error, "my_event", handler)
    assert error.__notes__ == ["raised by fail while handling the event 'my_event'"]


def test_add_error_note_other_event_adds_note() -> None:
    error = ValueError("boom")
    handler = fail
    _add_error_note(error, "my_event", handler)
    _add_error_note(error, "my_other_event", handler)
    assert error.__notes__ == [
        "raised by fail while handling the event 'my_event'",
        "raised by fail while handling the event 'my_other_event'",
    ]


def test_add_error_note_other_handler_adds_note() -> None:
    error = ValueError("boom")
    _add_error_note(error, "my_event", fail)
    _add_error_note(error, "my_event", hello_handler)
    assert error.__notes__ == [
        "raised by fail while handling the event 'my_event'",
        "raised by hello_handler while handling the event 'my_event'",
    ]


def failing_handler() -> None:
    msg = "handler failed"
    raise RuntimeError(msg)


##################################
#     Tests for Subscription     #
##################################


def test_subscription_repr() -> None:
    assert repr(Subscription(EventManager(), "my_event", print)) == (
        "Subscription(event='my_event', handler='print')"
    )


def test_subscription_repr_names_function_of_partial() -> None:
    subscription = Subscription(EventManager(), "my_event", functools.partial(print, "secret"))
    assert repr(subscription) == "Subscription(event='my_event', handler='print')"


def test_subscription_repr_names_class_of_callable_object() -> None:
    subscription = Subscription(EventManager(), "my_event", UninspectableCallable([]))
    assert repr(subscription) == "Subscription(event='my_event', handler='UninspectableCallable')"


def test_subscription_repr_ignores_repr_of_handler() -> None:
    assert repr(Subscription(EventManager(), "my_event", BadReprCallable())) == (
        "Subscription(event='my_event', handler='BadReprCallable')"
    )


def test_event_manager_get_subscriptions_repr_names_handlers() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", print)
    manager.add_event_handler("my_event", hello_handler)
    assert repr(manager.get_subscriptions("my_event")) == (
        "(Subscription(event='my_event', handler='print'), "
        "Subscription(event='my_event', handler='hello_handler'))"
    )


def test_subscription_event() -> None:
    assert Subscription(EventManager(), "my_event", print).event == "my_event"


def test_subscription_handler() -> None:
    handler = print
    assert Subscription(EventManager(), "my_event", handler).handler is handler


def test_subscription_once_default() -> None:
    assert not Subscription(EventManager(), "my_event", print).once


def test_subscription_once_true() -> None:
    assert Subscription(EventManager(), "my_event", print, once=True).once


def test_subscription_condition_default() -> None:
    assert Subscription(EventManager(), "my_event", print).condition is None


def test_subscription_condition() -> None:
    condition = PeriodicCondition(freq=2)
    assert Subscription(EventManager(), "my_event", print, condition=condition).condition is (
        condition
    )


def test_subscription_call_returns_handler_result() -> None:
    context = Context({"a": 1})
    assert (
        Subscription(EventManager(), "my_event", lambda context: context)._call(context) is context
    )


def test_subscription_call_removed_returns_none() -> None:
    subscription = EventManager().add_event_handler("my_event", hello_handler)
    subscription.remove()
    assert subscription._call(Context()) is None


def test_subscription_call_removed_does_not_call_handler() -> None:
    subscription = EventManager().add_event_handler("my_event", hello_handler)
    subscription.remove()
    subscription._call(Context())
    assert hello_handler.call_count == 0


def test_subscription_call_removed_does_not_evaluate_condition() -> None:
    condition = Mock(return_value=True)
    subscription = EventManager().add_event_handler("my_event", hello_handler, condition=condition)
    subscription.remove()
    subscription._call(Context())
    assert condition.call_count == 0


def test_subscription_call_condition_false_returns_none() -> None:
    subscription = Subscription(EventManager(), "my_event", lambda: 1, condition=lambda: False)
    assert subscription._call(Context()) is None


def test_subscription_call_condition_false_does_not_call_handler() -> None:
    subscription = Subscription(EventManager(), "my_event", hello_handler, condition=lambda: False)
    subscription._call(Context())
    assert hello_handler.call_count == 0


def test_subscription_call_condition_true_calls_handler() -> None:
    subscription = Subscription(EventManager(), "my_event", lambda: 1, condition=lambda: True)
    assert subscription._call(Context()) == 1


def test_subscription_call_condition_without_parameter_is_called_without_argument() -> None:
    subscription = Subscription(EventManager(), "my_event", lambda: 1, condition=lambda: True)
    assert subscription._call(Context({"a": 1})) == 1


def test_subscription_call_condition_with_parameter_receives_the_context() -> None:
    contexts: list[Context] = []

    def condition(context: Context) -> bool:
        contexts.append(context)
        return True

    context = Context({"a": 1})
    Subscription(EventManager(), "my_event", hello_handler, condition=condition)._call(context)
    assert contexts == [context]


def test_subscription_call_condition_with_parameter_true_calls_handler() -> None:
    subscription = Subscription(
        EventManager(), "my_event", lambda: 1, condition=lambda context: context["a"] == 1
    )
    assert subscription._call(Context({"a": 1})) == 1


def test_subscription_call_condition_with_parameter_false_returns_none() -> None:
    subscription = Subscription(
        EventManager(), "my_event", lambda: 1, condition=lambda context: context["a"] == 2
    )
    assert subscription._call(Context({"a": 1})) is None


def test_subscription_call_condition_with_parameter_false_does_not_call_handler() -> None:
    Subscription(
        EventManager(), "my_event", hello_handler, condition=lambda context: context["a"] == 2
    )._call(Context({"a": 1}))
    assert hello_handler.call_count == 0


def test_subscription_call_condition_with_parameter_and_handler_with_parameter() -> None:
    subscription = Subscription(
        EventManager(), "my_event", copy_context, condition=lambda context: "a" in context
    )
    assert subscription._call(Context({"a": 1})) == {"a": 1}


def test_subscription_call_condition_uninspectable_receives_the_context() -> None:
    calls: list[dict[str, Any]] = []
    Subscription(
        EventManager(), "my_event", hello_handler, condition=UninspectableCondition(calls)
    )._call(Context({"a": 1}))
    assert calls == [{"a": 1}]


def test_subscription_call_condition_with_parameter_does_not_consume_once() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler(
        "my_event", hello_handler, once=True, condition=lambda context: context["go"]
    )
    subscription._call(Context({"go": False}))
    assert subscription.active


def test_subscription_call_condition_with_parameter_raises() -> None:
    subscription = Subscription(
        EventManager(), "my_event", hello_handler, condition=lambda context: context["missing"]
    )
    with pytest.raises(KeyError, match=r"key 'missing' not found in the context"):
        subscription._call(Context({"a": 1}))


def test_subscription_call_condition_is_called_once() -> None:
    condition = Mock(return_value=True)
    Subscription(EventManager(), "my_event", hello_handler, condition=condition)._call(Context())
    assert condition.call_count == 1


def test_subscription_options_are_keyword_only() -> None:
    args: list[Any] = [EventManager(), "my_event", print, True]
    with pytest.raises(TypeError, match=r"positional arguments"):
        Subscription(*args)


def test_subscription_call_once_removes_registration() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", hello_handler, once=True)
    subscription._call(Context())
    assert not subscription.active


def test_subscription_call_once_calls_handler() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", lambda: 1, once=True)
    assert manager.get_subscriptions("my_event")[0]._call(Context()) == 1


def test_subscription_call_once_lost_claim_returns_none() -> None:
    manager = EventManager()
    subscriptions: list[Subscription] = []

    def condition() -> bool:
        subscriptions[0].remove()  # another thread wins the claim after the check
        return True

    subscriptions.append(
        manager.add_event_handler("my_event", lambda: 1, condition=condition, once=True)
    )
    assert subscriptions[0]._call(Context()) is None


def test_subscription_call_once_lost_claim_does_not_call_handler() -> None:
    manager = EventManager()
    subscriptions: list[Subscription] = []

    def condition() -> bool:
        subscriptions[0].remove()
        return True

    subscriptions.append(
        manager.add_event_handler("my_event", hello_handler, condition=condition, once=True)
    )
    subscriptions[0]._call(Context())
    assert hello_handler.call_count == 0


def test_subscription_call_once_removed_does_not_call_handler() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", hello_handler, once=True)
    subscription.remove()
    subscription._call(Context())
    assert hello_handler.call_count == 0


def test_subscription_call_not_once_keeps_registration() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", hello_handler)
    subscription._call(Context())
    assert subscription.active


def test_subscription_call_passes_the_whole_context() -> None:
    subscription = Subscription(EventManager(), "my_event", copy_context)
    assert subscription._call(Context({"a": 1, "b": 2})) == {"a": 1, "b": 2}


def test_subscription_call_without_parameter_calls_handler_without_argument() -> None:
    subscription = Subscription(EventManager(), "my_event", lambda: "called")
    assert subscription._call(Context({"a": 1})) == "called"


def test_subscription_call_uninspectable_handler_receives_context() -> None:
    calls: list[dict[str, Any]] = []
    Subscription(EventManager(), "my_event", UninspectableCallable(calls))._call(
        Context({"a": 1, "b": 2})
    )
    assert calls == [{"a": 1, "b": 2}]


##################################
#     Tests for _check_event     #
##################################


@pytest.mark.parametrize("event", ["my_event", ""])
def test_check_event_accepts_str(event: str) -> None:
    assert _check_event(event) is None


@pytest.mark.parametrize("event", [1, None, b"e"])
def test_check_event_rejects_non_str(event: object) -> None:
    with pytest.raises(TypeError, match=r"event must be a str, but got"):
        _check_event(event)


def test_check_event_error_names_the_type() -> None:
    with pytest.raises(TypeError, match=r"but got bytes"):
        _check_event(b"e")


####################################
#     Tests for _needs_context     #
####################################


def positional_handler(context: Context) -> None:
    logger.info("context %s", context)


def named_handler(first_name: str, last_name: str) -> None:
    r"""Implements a handler with two named arguments."""
    logger.info("Hello. I am %s %s", first_name, last_name)


def positional_only_handler(context: Context, /) -> None:
    logger.info("context %s", context)


def default_handler(context: Context | None = None) -> None:
    logger.info("context %s", context)


def keyword_only_handler(*, loss: float) -> None:
    logger.info("loss %s", loss)


def kwargs_handler(**kwargs: Any) -> None:
    logger.info("Kwargs: %s", kwargs)


class UninspectableCondition:
    r"""Implements a condition whose signature cannot be inspected."""

    __signature__ = 1

    def __init__(self, calls: list[dict[str, Any]]) -> None:
        self._calls = calls

    def __call__(self, context: Context) -> bool:
        self._calls.append(dict(context))
        return True


class UninspectableCallable:
    r"""Implements a callable whose signature cannot be inspected."""

    __signature__ = 1

    def __init__(self, calls: list[dict[str, Any]]) -> None:
        self._calls = calls

    def __call__(self, context: Context) -> None:
        self._calls.append(dict(context))


def test_needs_context_no_parameter() -> None:
    assert not _needs_context(hello_handler)


def test_needs_context_positional_or_keyword() -> None:
    assert _needs_context(positional_handler)


def test_needs_context_positional_only() -> None:
    assert _needs_context(positional_only_handler)


def test_needs_context_parameter_with_default() -> None:
    assert _needs_context(default_handler)


def test_needs_context_var_positional() -> None:
    assert _needs_context(payload_handler)


def test_needs_context_keyword_only() -> None:
    assert not _needs_context(keyword_only_handler)


def test_needs_context_var_keyword() -> None:
    assert not _needs_context(kwargs_handler)


def test_needs_context_uninspectable() -> None:
    assert _needs_context(UninspectableCallable([]))


def test_needs_context_two_parameters() -> None:
    assert _needs_context(named_handler)


def test_needs_context_partial_binding_the_only_positional_argument() -> None:
    assert not _needs_context(functools.partial(positional_handler, Context()))


def test_needs_context_partial_binding_one_of_two_positional_arguments() -> None:
    assert _needs_context(functools.partial(named_handler, "John"))


def test_needs_context_partial_binding_keyword_argument_of_the_context() -> None:
    assert not _needs_context(functools.partial(positional_handler, context=Context()))


def test_needs_context_method() -> None:
    assert _needs_context(CallableRecorder([]))


def test_needs_context_bound_method_without_parameter() -> None:
    assert not _needs_context(CustomCondition())


def test_needs_context_lambda_without_parameter() -> None:
    assert not _needs_context(lambda: None)


def test_needs_context_lambda_with_parameter() -> None:
    assert _needs_context(lambda context: context)


#################################
#     Tests for _as_context     #
#################################


def test_as_context_dict() -> None:
    assert _as_context({"a": 1, "b": 2}) == {"a": 1, "b": 2}


def test_as_context_dict_is_a_context() -> None:
    assert isinstance(_as_context({"a": 1}), Context)


def test_as_context_dict_is_copied() -> None:
    data: dict[str, object] = {"a": 1}
    context = _as_context(data)
    data["b"] = 2
    assert dict(context) == {"a": 1}


def test_as_context_dict_is_not_modified() -> None:
    data: dict[str, object] = {"a": 1}
    _as_context(data)
    assert data == {"a": 1}


def test_as_context_empty_dict() -> None:
    assert _as_context({}) == {}


def test_as_context_none() -> None:
    assert _as_context(None) == {}


def test_as_context_none_is_shared() -> None:
    assert _as_context(None) is _as_context(None)


def test_as_context_context_is_reused() -> None:
    context = Context({"a": 1})
    assert _as_context(context) is context


def test_as_context_other_mapping() -> None:
    assert _as_context(MappingProxyType({"a": 1})) == {"a": 1}


@pytest.mark.parametrize("context", [1, "abc", [("a", 1)], 1.5])
def test_as_context_invalid_type(context: Any) -> None:
    with pytest.raises(TypeError, match=r"context must be a mapping or None, but got"):
        _as_context(context)


def test_as_context_invalid_type_names_the_type() -> None:
    with pytest.raises(TypeError, match=r"but got list"):
        _as_context([])


@pytest.mark.parametrize("key", [1, None, b"a"])
def test_as_context_invalid_key(key: Any) -> None:
    with pytest.raises(TypeError, match=r"the keys of data must be str, but got"):
        _as_context({key: 1})


####################################################
#     Tests for the context given to a trigger     #
####################################################


def test_event_manager_trigger_event_context_object_is_passed_as_is() -> None:
    manager = EventManager()
    contexts: list[Context] = []
    manager.add_event_handler("my_event", contexts.append)
    context = Context({"epoch": 3})
    manager.trigger_event("my_event", context)
    assert contexts[0] is context


@pytest.mark.parametrize("data", [{"epoch": 3, "loss": 0.5}, Context({"epoch": 3, "loss": 0.5})])
def test_event_manager_trigger_event_dict_and_context_give_the_same_data(data: Any) -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler)
    manager.trigger_event("my_event", data)
    assert payload_handler.args == ({"epoch": 3, "loss": 0.5},)


@pytest.mark.parametrize("data", [{"epoch": 3}, Context({"epoch": 3})])
async def test_event_manager_atrigger_event_dict_and_context_give_the_same_data(data: Any) -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler)
    await manager.atrigger_event("my_event", data)
    assert payload_handler.args == ({"epoch": 3},)


def test_event_manager_trigger_event_context_can_be_reused() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler)
    context = Context({"epoch": 3})
    manager.trigger_event("my_event", context)
    manager.trigger_event("my_event", context)
    assert payload_handler.call_count == 2


def test_event_manager_trigger_event_dict_is_not_modified_by_a_handler() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", copy_context)
    data = {"epoch": 3}
    manager.trigger_event("my_event", data)
    assert data == {"epoch": 3}


def test_event_manager_trigger_event_keys_need_not_be_identifiers() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler)
    manager.trigger_event("my_event", {"train/loss": 0.5, "event": "x"})
    assert payload_handler.args == ({"train/loss": 0.5, "event": "x"},)


def test_event_manager_trigger_event_context_none() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler)
    manager.trigger_event("my_event", None)
    assert payload_handler.args == ({},)


@pytest.mark.parametrize("context", [1, "abc", [("a", 1)]])
def test_event_manager_trigger_event_invalid_context(context: Any) -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler)
    with pytest.raises(TypeError, match=r"context must be a mapping or None, but got"):
        manager.trigger_event("my_event", context)
    assert hello_handler.call_count == 0


def test_event_manager_trigger_event_invalid_key() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler)
    context: Any = {1: "a"}
    with pytest.raises(TypeError, match=r"the keys of data must be str, but got 1"):
        manager.trigger_event("my_event", context)
    assert hello_handler.call_count == 0


def test_event_manager_trigger_event_keyword_payload_is_rejected() -> None:
    manager = EventManager()
    payload: Any = {"epoch": 3}
    with pytest.raises(TypeError, match=r"got an unexpected keyword argument 'epoch'"):
        manager.trigger_event("my_event", **payload)


def test_subscription_active_after_add() -> None:
    assert EventManager().add_event_handler("my_event", print).active


def test_subscription_active_never_registered() -> None:
    assert Subscription(EventManager(), "my_event", print).active


def test_subscription_active_false_after_remove() -> None:
    subscription = EventManager().add_event_handler("my_event", print)
    subscription.remove()
    assert not subscription.active


def test_subscription_active_other_subscription_removed() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", print).remove()
    assert manager.add_event_handler("my_event", print).active


def test_subscription_active_other_event_cleared() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", print)
    manager.clear_event("my_other_event")
    assert subscription.active


def test_subscription_remove_returns_true() -> None:
    assert EventManager().add_event_handler("my_event", print).remove()


def test_subscription_remove_twice_returns_false() -> None:
    subscription = EventManager().add_event_handler("my_event", print)
    subscription.remove()
    assert not subscription.remove()


def test_subscription_remove_inactive_after_remove() -> None:
    subscription = EventManager().add_event_handler("my_event", print)
    subscription.remove()
    assert not subscription.active


def test_subscription_remove_removes_from_manager() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", print).remove()
    assert len(manager) == 0


def test_subscription_remove_middle_keeps_order() -> None:
    manager = EventManager()
    first = manager.add_event_handler("my_event", print)
    second = manager.add_event_handler("my_event", print)
    third = manager.add_event_handler("my_event", print)
    second.remove()
    assert manager.get_subscriptions("my_event") == (first, third)


def test_subscription_remove_first_and_last_keeps_middle() -> None:
    manager = EventManager()
    first = manager.add_event_handler("my_event", print)
    second = manager.add_event_handler("my_event", print)
    third = manager.add_event_handler("my_event", print)
    first.remove()
    third.remove()
    assert manager.get_subscriptions("my_event") == (second,)


def test_subscription_remove_same_handler_registered_three_times_removes_second() -> None:
    manager = EventManager()
    handler = print
    first = manager.add_event_handler("my_event", handler)
    second = manager.add_event_handler("my_event", handler)
    third = manager.add_event_handler("my_event", handler)
    second.remove()
    assert manager.get_subscriptions("my_event") == (first, third)


def test_subscription_remove_not_registered_returns_false() -> None:
    subscription = Subscription(EventManager(), "my_event", print)
    assert not subscription.remove()


def test_subscription_remove_not_registered_keeps_other_registration() -> None:
    manager = EventManager()
    registered = manager.add_event_handler("my_event", print)
    Subscription(manager, "my_event", print).remove()
    assert manager.get_subscriptions("my_event") == (registered,)


def test_subscription_is_hashable_by_identity() -> None:
    manager = EventManager()
    handler = print
    first = manager.add_event_handler("my_event", handler)
    second = manager.add_event_handler("my_event", handler)
    assert len({first, second}) == 2


def test_subscription_remove_same_handler_registered_twice_keeps_other_registration() -> None:
    manager = EventManager()
    handler = print
    first = manager.add_event_handler("my_event", handler)
    manager.add_event_handler("my_event", handler)
    first.remove()
    first.remove()
    assert len(manager) == 1


def test_subscription_remove_same_handler_registered_twice_second_stays_active() -> None:
    manager = EventManager()
    handler = print
    first = manager.add_event_handler("my_event", handler)
    second = manager.add_event_handler("my_event", handler)
    first.remove()
    first.remove()
    assert second.active


def test_subscription_inactive_after_clear_event() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", print)
    manager.clear_event("my_event")
    assert not subscription.active


def test_subscription_remove_after_clear_event_returns_false() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", print)
    manager.clear_event("my_event")
    assert not subscription.remove()


def test_subscription_inactive_after_reset() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", print)
    manager.reset()
    assert not subscription.active


def test_subscription_enter_returns_subscription() -> None:
    subscription = EventManager().add_event_handler("my_event", print)
    with subscription as entered:
        assert entered is subscription


def test_subscription_exit_removes() -> None:
    manager = EventManager()
    with manager.add_event_handler("my_event", print):
        pass
    assert len(manager) == 0


def test_subscription_exit_does_not_swallow_exception_of_block() -> None:
    with (
        pytest.raises(RuntimeError, match=r"handler failed"),
        EventManager().add_event_handler("my_event", print),
    ):
        failing_handler()


def test_subscription_exit_removes_when_block_raises() -> None:
    manager = EventManager()
    with (
        pytest.raises(RuntimeError, match=r"handler failed"),
        manager.add_event_handler("my_event", print),
    ):
        failing_handler()
    assert len(manager) == 0


##########################################
#     Tests for _check_not_awaitable     #
##########################################


def test_check_not_awaitable_none() -> None:
    assert _check_not_awaitable(None, print) is None


def test_check_not_awaitable_value() -> None:
    assert _check_not_awaitable(1, print) is None


def test_check_not_awaitable_coroutine_raises() -> None:
    async def coroutine_handler() -> None:
        r"""Implement a coroutine handler."""
        return

    with pytest.raises(TypeError, match=r"returned an awaitable; use atrigger_event"):
        _check_not_awaitable(coroutine_handler(), coroutine_handler)


def test_check_not_awaitable_closes_coroutine() -> None:
    async def coroutine_handler() -> None:
        r"""Implement a coroutine handler."""
        return

    coroutine = coroutine_handler()
    with pytest.raises(TypeError, match=r"returned an awaitable"):
        _check_not_awaitable(coroutine, coroutine_handler)
    assert inspect.getcoroutinestate(coroutine) == "CORO_CLOSED"


def test_check_not_awaitable_message_names_function() -> None:
    handler = functools.partial(async_handler_with_argument, "secret")
    with pytest.raises(
        TypeError, match=r"^async_handler_with_argument returned an awaitable; use atrigger_event$"
    ):
        _check_not_awaitable(handler(), handler)


def test_check_not_awaitable_ignores_repr_of_handler() -> None:
    with pytest.raises(
        TypeError, match=r"^BadReprCallable returned an awaitable; use atrigger_event$"
    ):
        _check_not_awaitable(Mock(spec=Awaitable), BadReprCallable())


def test_check_not_awaitable_future_raises() -> None:
    future: Any = Mock(spec=Awaitable)
    with pytest.raises(TypeError, match=r"returned an awaitable"):
        _check_not_awaitable(future, print)


###############################################
#     Tests for the flag and the registry     #
###############################################


def flag_and_registry(manager: EventManager, subscription: Subscription) -> tuple[bool, bool]:
    r"""Gets the flag of a registration and its presence in the
    manager."""
    return subscription.active, subscription in manager.get_subscriptions(subscription.event)


def test_flag_and_registry_agree_before_removal() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", print)
    assert flag_and_registry(manager, subscription) == (True, True)


def test_flag_and_registry_agree_after_remove() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", print)
    subscription.remove()
    assert flag_and_registry(manager, subscription) == (False, False)


def test_flag_and_registry_agree_after_exit() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", print)
    with subscription:
        pass
    assert flag_and_registry(manager, subscription) == (False, False)


def test_flag_and_registry_agree_after_clear_event() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", print)
    manager.clear_event("my_event")
    assert flag_and_registry(manager, subscription) == (False, False)


def test_flag_and_registry_agree_after_reset() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", print)
    manager.reset()
    assert flag_and_registry(manager, subscription) == (False, False)


def test_flag_and_registry_agree_after_clear_other_event() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", print)
    manager.clear_event("other_event")
    assert flag_and_registry(manager, subscription) == (True, True)
