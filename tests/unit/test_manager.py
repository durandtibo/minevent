from __future__ import annotations

import copy
import dataclasses
import functools
import logging
import pickle
import threading
from enum import Enum, StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock, create_autospec

import pytest

from minevent import (
    Context,
    EventManager,
    PeriodicCondition,
    Subscription,
)
from minevent.manager import _as_context, _check_event
from tests.unit.handlers import (
    AsyncConditionMethod,
    AsyncConditionObject,
    AwaitableResult,
    CallableRecorder,
    CustomCondition,
    ModelStandIn,
    async_condition,
    condition_returning_a_coroutine,
    copy_context,
    fail,
    generator_handler,
    has_payload,
    hello_handler,
    named_handler,
    noop_handler,
    payload_handler,
    read_epoch,
    requires_lazy_annotations,
    unresolved_function,
)
from tests.unit.utils import raised, trace

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


logger = logging.getLogger(__name__)


EVENTS = ("my_event", "my_other_event")


def registered_subscription(manager: EventManager) -> Subscription:
    r"""Return the first ``Subscription`` registered to ``my_event``."""
    return manager.get_subscriptions("my_event")[0]


def add_hello_handler_when_triggered(manager: EventManager) -> None:
    r"""Register a handler that adds ``hello_handler`` to
    ``my_event``."""
    manager.add_event_handler(
        "my_event", lambda: manager.add_event_handler("my_event", hello_handler)
    )


async def async_handler_with_argument(secret: str) -> None:
    r"""Implement a coroutine handler that has an argument."""


@trace
def positional_bound_handler(first: int, second: int, context: Context) -> None:
    r"""Implements a handler that receives two bound values and the
    context."""
    logger.info("Payload: %s %s %s", first, second, context)


@trace
def keyword_bound_handler(context: Context, *, k: int = 0) -> None:
    r"""Implements a handler that receives the context and a keyword
    value."""
    logger.info("Payload: %s %s", context, k)


INVALID_EVENTS = [1, None, b"my_event"]


INVALID_HANDLERS = [None, "handler", 5, EventManager()]


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


def fail_with_argument(value: object) -> None:
    r"""Implements a handler with an argument that raises a
    ``ValueError``."""
    msg = f"boom {type(value).__qualname__}"
    raise ValueError(msg)


class BadReprAwaitableCallable:
    r"""Implement a handler whose ``repr`` raises and that returns an
    awaitable."""

    def __repr__(self) -> str:
        msg = "repr failed"
        raise RuntimeError(msg)

    def __call__(self) -> object:
        r"""Return an awaitable."""
        return AwaitableResult()


@dataclasses.dataclass(frozen=True)
class FrozenError(Exception):
    r"""Implement an exception that forbids new attributes."""

    code: int = 1


def failing_condition() -> bool:
    r"""Implement a condition that raises a ``ValueError``."""
    msg = "boom"
    raise ValueError(msg)


class StrEvent(StrEnum):
    r"""Implement event names that are strings."""

    EPOCH_END = "epoch_end"


class PlainEvent(Enum):
    r"""Implement event names with ``str`` values that are not
    strings."""

    EPOCH_END = "epoch_end"


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
    event_manager.add_event_handler("other_event", noop_handler)
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
    manager.add_event_handler("my_event", create_autospec(read_epoch, side_effect=error))
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
    event_manager.add_event_handler("my_event", create_autospec(read_epoch, side_effect=error))
    assert raised(event_manager.trigger_event, "my_event") is error


def test_event_manager_trigger_event_base_exception_has_no_note() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler(
        "my_event", create_autospec(read_epoch, side_effect=KeyboardInterrupt("interrupted"))
    )
    assert not hasattr(raised(event_manager.trigger_event, "my_event"), "__notes__")


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
    manager.add_event_handler("my_event", functools.partial(positional_bound_handler, 1, 2))
    manager.trigger_event("my_event", {"epoch": 3})
    assert positional_bound_handler.args == (1, 2, {"epoch": 3})


def test_event_manager_add_event_handler_partial_binds_keyword_argument() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", functools.partial(keyword_bound_handler, k=1))
    manager.trigger_event("my_event", {"epoch": 3})
    assert (keyword_bound_handler.args, keyword_bound_handler.kwargs) == (({"epoch": 3},), {"k": 1})


def test_event_manager_add_event_handler_payload_does_not_override_keyword_bound_by_partial() -> (
    None
):
    manager = EventManager()
    manager.add_event_handler("my_event", functools.partial(keyword_bound_handler, k=1))
    manager.trigger_event("my_event", {"k": 2})
    assert (keyword_bound_handler.args, keyword_bound_handler.kwargs) == (({"k": 2},), {"k": 1})


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


def test_event_manager_contains_non_str() -> None:
    manager = EventManager()
    manager.add_event_handler("1", noop_handler)
    assert 1 not in manager


def test_event_manager_str_enum_event_is_kept_as_given() -> None:
    manager = EventManager()
    manager.add_event_handler(StrEvent.EPOCH_END, noop_handler)
    assert manager.events[0] is StrEvent.EPOCH_END


def test_event_manager_str_enum_event_matches_its_value() -> None:
    manager = EventManager()
    manager.add_event_handler(StrEvent.EPOCH_END, hello_handler)
    manager.trigger_event("epoch_end")
    assert hello_handler.call_count == 1


def test_event_manager_plain_enum_event_is_rejected() -> None:
    event: Any = PlainEvent.EPOCH_END
    with pytest.raises(TypeError, match=r"^event must be a str, but got PlainEvent$"):
        EventManager().add_event_handler(event, noop_handler)


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
    manager.add_event_handler("my_event", functools.partial(payload_handler))
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


def test_event_manager_trigger_event_runs_handler_without_lock() -> None:
    manager = EventManager()
    lock_held: list[bool] = []
    manager.add_event_handler("my_event", lambda: lock_held.append(lock_is_held(manager)))
    manager.trigger_event("my_event")
    assert lock_held == [False]


class LockRecorder:
    r"""Implement a handler whose finalizer records if the lock of the
    manager is held."""

    def __init__(self, manager: EventManager, lock_held: list[bool]) -> None:
        self._manager = manager
        self._lock_held = lock_held

    def __del__(self) -> None:
        self._lock_held.append(lock_is_held(self._manager))

    def __call__(self) -> bool:
        r"""Implement a handler, or a condition that is ``True``."""
        return True


def test_event_manager_clear_event_releases_handlers_without_lock() -> None:
    manager = EventManager()
    lock_held: list[bool] = []
    manager.add_event_handler("my_event", LockRecorder(manager, lock_held))
    manager.add_event_handler("my_event", LockRecorder(manager, lock_held))
    manager.clear_event("my_event")
    assert lock_held == [False, False]


def test_event_manager_reset_releases_handlers_without_lock() -> None:
    manager = EventManager()
    lock_held: list[bool] = []
    manager.add_event_handler("my_event", LockRecorder(manager, lock_held))
    manager.add_event_handler("my_other_event", LockRecorder(manager, lock_held))
    manager.reset()
    assert lock_held == [False, False]


def test_event_manager_clear_event_releases_conditions_without_lock() -> None:
    manager = EventManager()
    lock_held: list[bool] = []
    manager.add_event_handler("my_event", noop_handler, condition=LockRecorder(manager, lock_held))
    manager.add_event_handler("my_event", noop_handler, condition=LockRecorder(manager, lock_held))
    manager.clear_event("my_event")
    assert lock_held == [False, False]


def test_event_manager_remove_releases_handler_without_lock() -> None:
    manager = EventManager()
    lock_held: list[bool] = []
    manager.add_event_handler("my_event", LockRecorder(manager, lock_held)).remove()
    assert lock_held == [False]


def test_event_manager_reset_keeps_working() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", noop_handler)
    manager.reset()
    manager.add_event_handler("my_event", hello_handler)
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


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


@pytest.mark.parametrize(("epoch", "call_count"), [(0, 0), (1, 0), (2, 1), (3, 1)])
def test_event_manager_trigger_event_condition_reads_the_payload(
    epoch: int, call_count: int
) -> None:
    manager = EventManager()
    manager.add_event_handler(
        "my_event", hello_handler, condition=lambda context: context.get("epoch", 0) >= 2
    )
    manager.trigger_event("my_event", {"epoch": epoch})
    assert hello_handler.call_count == call_count


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


def test_event_manager_trigger_event_note_ignores_repr_of_arguments() -> None:
    class BadRepr:
        def __repr__(self) -> str:
            msg = "repr failed"
            raise RuntimeError(msg)

    manager = EventManager()
    manager.add_event_handler("my_event", functools.partial(fail_with_argument, BadRepr()))
    with pytest.raises(ValueError, match=r"boom"):
        manager.trigger_event("my_event")


def test_event_manager_trigger_event_note_is_short_for_large_arguments() -> None:
    manager = EventManager()
    manager.add_event_handler(
        "my_event", functools.partial(fail_with_argument, list(range(10_000)))
    )
    assert len(raised(manager.trigger_event, "my_event").__notes__[0]) < 100


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


######################################################
#     Tests for the signatures of a registration     #
######################################################


@requires_lazy_annotations
def test_event_manager_add_event_handler_unresolved_annotation(tmp_path: Path) -> None:
    handler = unresolved_function(tmp_path, "no_parameter")
    subscription = EventManager().add_event_handler("my_event", handler)
    assert subscription.active


@requires_lazy_annotations
def test_event_manager_add_event_handler_condition_unresolved_annotation(tmp_path: Path) -> None:
    condition = unresolved_function(tmp_path, "no_parameter")
    subscription = EventManager().add_event_handler("my_event", noop_handler, condition=condition)
    assert subscription.active


@pytest.mark.parametrize("handler", [print, named_handler, generator_handler])
def test_event_manager_add_event_handler_rejected_handler_leaves_manager_unchanged(
    handler: Callable[..., object],
) -> None:
    manager = EventManager()
    with pytest.raises(TypeError, match=r"^handler "):
        manager.add_event_handler("my_event", handler)
    assert len(manager) == 0


@pytest.mark.parametrize("condition", [Mock(), named_handler, generator_handler])
def test_event_manager_add_event_handler_rejected_condition_leaves_manager_unchanged(
    condition: Any,
) -> None:
    manager = EventManager()
    with pytest.raises(TypeError, match=r"^condition "):
        manager.add_event_handler("my_event", noop_handler, condition=condition)
    assert len(manager) == 0


@pytest.mark.parametrize(
    "condition",
    [async_condition, AsyncConditionMethod().check, functools.partial(async_condition)],
)
def test_event_manager_add_event_handler_async_condition(condition: Any) -> None:
    manager = EventManager()
    with pytest.raises(TypeError, match=r"^condition must be synchronous, but got "):
        manager.add_event_handler("my_event", noop_handler, condition=condition)
    assert len(manager) == 0


def test_event_manager_on_async_condition() -> None:
    manager = EventManager()
    condition: Any = async_condition
    decorator = manager.on("my_event", condition=condition)
    with pytest.raises(TypeError, match=r"^condition must be synchronous, but got async_condition"):
        decorator(noop_handler)
    assert len(manager) == 0


def test_event_manager_on_rejected_signature() -> None:
    manager = EventManager()
    decorator = manager.on("my_event")
    handler: Any = named_handler
    with pytest.raises(TypeError, match=r"^handler named_handler must need no argument"):
        decorator(handler)
    assert len(manager) == 0


def test_event_manager_on_rejected_condition_signature() -> None:
    manager = EventManager()
    decorator = manager.on("my_event", condition=Mock())
    with pytest.raises(TypeError, match=r"^condition Mock must need no argument"):
        decorator(noop_handler)
    assert len(manager) == 0


def test_event_manager_trigger_event_keeps_the_default_of_a_bound_method() -> None:
    model = ModelStandIn()
    manager = EventManager()
    manager.add_event_handler("my_event", model.train)
    manager.trigger_event("my_event", {"epoch": 3})
    assert model.mode is True


def test_event_manager_trigger_event_keeps_the_default_arguments_of_lambdas() -> None:
    values: list[object] = []
    manager = EventManager()
    manager.add_event_handler("my_event", lambda i=0: values.append(i))
    manager.add_event_handler("my_event", lambda i=1: values.append(i))
    manager.trigger_event("my_event", {"epoch": 3})
    assert values == [0, 1]


def test_event_manager_trigger_event_condition_keeps_its_default_argument() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler, condition=lambda flag=False: flag)
    manager.trigger_event("my_event", {"epoch": 3})
    assert hello_handler.call_count == 0


def test_event_manager_trigger_event_optional_parameter_does_not_receive_the_context() -> None:
    values: list[object] = []

    def handler(context: object = None) -> None:
        values.append(context)

    manager = EventManager()
    manager.add_event_handler("my_event", handler)
    manager.trigger_event("my_event", {"epoch": 3})
    assert values == [None]


def test_event_manager_trigger_event_context_before_a_default_argument() -> None:
    values: list[object] = []
    manager = EventManager()
    manager.add_event_handler("my_event", lambda context, i=1: values.append((dict(context), i)))
    manager.trigger_event("my_event", {"epoch": 3})
    assert values == [({"epoch": 3}, 1)]


def test_event_manager_trigger_event_autospec_handler() -> None:
    handler = create_autospec(read_epoch)
    manager = EventManager()
    manager.add_event_handler("my_event", handler)
    manager.trigger_event("my_event", {"epoch": 3})
    handler.assert_called_once_with({"epoch": 3})


############################################
#     Tests for an awaitable condition     #
############################################


@pytest.mark.parametrize("condition", [AsyncConditionObject(), condition_returning_a_coroutine])
def test_event_manager_trigger_event_condition_returns_awaitable(condition: Any) -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler, condition=condition)
    with pytest.raises(TypeError, match=r"^condition .+ returned an awaitable"):
        manager.trigger_event("my_event")
    assert hello_handler.call_count == 0


def test_event_manager_trigger_event_condition_awaitable_keeps_once_registration() -> None:
    manager = EventManager()
    condition: Any = condition_returning_a_coroutine
    subscription = manager.add_event_handler(
        "my_event", hello_handler, once=True, condition=condition
    )
    with pytest.raises(TypeError, match=r"returned an awaitable"):
        manager.trigger_event("my_event")
    assert subscription.active


def test_event_manager_trigger_event_condition_awaitable_has_note() -> None:
    manager = EventManager()
    condition: Any = condition_returning_a_coroutine
    manager.add_event_handler("my_event", noop_handler, condition=condition)
    assert raised(manager.trigger_event, "my_event").__notes__ == [
        (
            "raised by the condition condition_returning_a_coroutine of noop_handler "
            "while handling the event 'my_event'"
        )
    ]


def test_event_manager_trigger_event_removed_registration_does_not_evaluate_condition() -> None:
    manager = EventManager()
    condition = create_autospec(has_payload, return_value=True)
    manager.add_event_handler("my_event", lambda: manager.clear_event("my_event"))
    manager.add_event_handler("my_event", noop_handler, condition=condition)
    manager.trigger_event("my_event")
    assert condition.call_count == 0


@pytest.mark.parametrize("once", [True, False])
def test_event_manager_trigger_event_condition_removes_registration(once: bool) -> None:
    manager = EventManager()

    def condition() -> bool:
        return manager.get_subscriptions("my_event")[0].remove()

    manager.add_event_handler("my_event", hello_handler, once=once, condition=condition)
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 0


@pytest.mark.parametrize("once", [True, False])
def test_event_manager_trigger_event_condition_resets_manager(once: bool) -> None:
    manager = EventManager()

    def condition() -> bool:
        manager.reset()
        return True

    manager.add_event_handler("my_event", hello_handler, once=once, condition=condition)
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 0


def test_event_manager_trigger_event_condition_removes_registration_runs_next_handler() -> None:
    manager = EventManager()

    def condition() -> bool:
        return manager.get_subscriptions("my_event")[0].remove()

    manager.add_event_handler("my_event", noop_handler, condition=condition)
    manager.add_event_handler("my_event", hello_handler)
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


#############################
#     Tests for _remove     #
#############################


def test_remove_removes_the_registration() -> None:
    manager = EventManager()
    first = manager.add_event_handler("my_event", noop_handler)
    second = manager.add_event_handler("my_event", noop_handler)
    manager._remove(first)
    assert manager.get_subscriptions("my_event") == (second,)


def test_remove_returns_true() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", noop_handler)
    assert manager._remove(subscription)


def test_remove_deactivates_the_registration() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", noop_handler)
    manager._remove(subscription)
    assert not subscription.active


def test_remove_already_removed_returns_false() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", noop_handler)
    manager._remove(subscription)
    assert not manager._remove(subscription)


def test_remove_already_removed_keeps_the_other_registrations() -> None:
    manager = EventManager()
    first = manager.add_event_handler("my_event", noop_handler)
    second = manager.add_event_handler("my_event", noop_handler)
    manager._remove(first)
    manager._remove(first)
    assert manager.get_subscriptions("my_event") == (second,)


def test_remove_last_registration_drops_the_event() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", noop_handler)
    manager._remove(subscription)
    assert manager.events == []


def test_remove_keeps_the_other_events() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", noop_handler)
    manager.add_event_handler("my_other_event", noop_handler)
    manager._remove(subscription)
    assert manager.events == ["my_other_event"]


def test_remove_unknown_event_returns_false() -> None:
    subscription = Subscription(EventManager(), "my_event", noop_handler)
    assert not EventManager()._remove(subscription)


def test_remove_never_registered_stays_active() -> None:
    manager = EventManager()
    subscription = Subscription(manager, "my_event", noop_handler)
    manager._remove(subscription)
    assert subscription.active


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


#################################################
#     Tests for the notes of the exceptions     #
#################################################


def test_event_manager_trigger_event_awaitable_names_function_of_partial() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", functools.partial(async_handler_with_argument, "secret"))
    with pytest.raises(
        TypeError, match=r"^async_handler_with_argument returned an awaitable; use atrigger_event"
    ):
        manager.trigger_event("my_event")


def test_event_manager_trigger_event_awaitable_ignores_repr_of_handler() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", BadReprAwaitableCallable())
    with pytest.raises(
        TypeError,
        match=r"^BadReprAwaitableCallable returned an awaitable; use atrigger_event",
    ):
        manager.trigger_event("my_event")


def test_event_manager_trigger_event_condition_raises_note_names_condition() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", noop_handler, condition=failing_condition)
    assert raised(manager.trigger_event, "my_event").__notes__ == [
        (
            "raised by the condition failing_condition of noop_handler "
            "while handling the event 'my_event'"
        )
    ]


def test_event_manager_trigger_event_handler_raises_after_condition_note() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", fail, condition=lambda: True)
    assert raised(manager.trigger_event, "my_event").__notes__ == [
        "raised by fail while handling the event 'my_event'"
    ]


def test_event_manager_trigger_event_condition_raises_skips_next_handlers() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", noop_handler, condition=failing_condition)
    manager.add_event_handler("my_event", hello_handler)
    with pytest.raises(ValueError, match=r"boom"):
        manager.trigger_event("my_event")
    assert hello_handler.call_count == 0


@pytest.mark.parametrize("option", ["handler", "condition"])
def test_event_manager_trigger_event_frozen_exception_is_unchanged(option: str) -> None:
    error = FrozenError()
    raising = create_autospec(noop_handler, side_effect=error)
    manager = EventManager()
    options: dict[str, Any] = {"handler": noop_handler, option: raising}
    manager.add_event_handler("my_event", **options)
    assert raised(manager.trigger_event, "my_event") is error
