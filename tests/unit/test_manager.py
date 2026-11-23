from __future__ import annotations

import contextlib
import copy
import functools
import inspect
import logging
import pickle
import threading
from collections.abc import Awaitable
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock

import pytest

from minevent import (
    EventManager,
    PeriodicCondition,
    Subscription,
)
from minevent.manager import (
    _accepted_keywords,
    _add_error_note,
    _check_not_awaitable,
    _describe,
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


def test_event_manager_trigger_event_handler_removed_during_dispatch_still_runs() -> None:
    event_manager = EventManager()
    subscriptions: list[Subscription] = []

    def remove_hello() -> None:
        subscriptions[0].remove()

    event_manager.add_event_handler("my_event", remove_hello)
    subscriptions.append(event_manager.add_event_handler("my_event", hello_handler))
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
    with contextlib.suppress(ValueError):
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
    with contextlib.suppress(TypeError):
        manager.add_event_handler("my_event", handler)
    assert len(manager) == 0


@pytest.mark.parametrize("handler", INVALID_HANDLERS)
def test_event_manager_on_handler_must_be_callable(handler: Any) -> None:
    with pytest.raises(TypeError, match=r"handler must be callable"):
        EventManager().on("my_event")(handler)


def test_event_manager_on_invalid_handler_is_not_registered() -> None:
    manager = EventManager()
    handler: Any = 5
    with contextlib.suppress(TypeError):
        manager.on("my_event")(handler)
    assert len(manager) == 0


def test_event_manager_add_event_handler_condition_must_be_callable() -> None:
    condition: Any = 5
    with pytest.raises(TypeError, match=r"condition must be callable"):
        EventManager().add_event_handler("my_event", hello_handler, condition=condition)


def test_event_manager_add_event_handler_invalid_condition_is_not_registered() -> None:
    manager = EventManager()
    condition: Any = 5
    with contextlib.suppress(TypeError):
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
    manager.trigger_event("my_event", epoch=3)
    assert calls == [{"epoch": 3}]


def test_event_manager_add_event_handler_event_handler_still_accepted() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler)
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


def test_event_manager_add_event_handler_partial_binds_positional_argument() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", functools.partial(payload_handler, 1, 2))
    manager.trigger_event("my_event", epoch=3)
    assert (payload_handler.args, payload_handler.kwargs) == ((1, 2), {"epoch": 3})


def test_event_manager_add_event_handler_partial_binds_keyword_argument() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", functools.partial(payload_handler, k=1))
    manager.trigger_event("my_event", epoch=3)
    assert payload_handler.kwargs == {"k": 1, "epoch": 3}


def test_event_manager_add_event_handler_payload_overrides_keyword_bound_by_partial() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", functools.partial(payload_handler, k=1))
    manager.trigger_event("my_event", k=2)
    assert payload_handler.kwargs == {"k": 2}


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


def test_event_manager_add_event_handler_filter_payload_passes_accepted_keys_only() -> None:
    manager = EventManager()
    epochs: list[int] = []

    def log_epoch(epoch: int) -> None:
        epochs.append(epoch)

    manager.add_event_handler("my_event", log_epoch, filter_payload=True)
    manager.trigger_event("my_event", epoch=3, loss=0.5)
    assert epochs == [3]


def test_event_manager_add_event_handler_filter_payload_drops_key_bound_by_partial() -> None:
    manager = EventManager()
    calls: list[tuple[int, int]] = []

    def record(a: int, b: int) -> None:
        calls.append((a, b))

    manager.add_event_handler("my_event", functools.partial(record, 1), filter_payload=True)
    manager.trigger_event("my_event", a=9, b=2)
    assert calls == [(1, 2)]


def test_event_manager_add_event_handler_filter_payload_keyword_bound_by_partial_is_overridden() -> (
    None
):
    manager = EventManager()
    calls: list[tuple[int, int]] = []

    def record(a: int, b: int) -> None:
        calls.append((a, b))

    manager.add_event_handler("my_event", functools.partial(record, b=1), filter_payload=True)
    manager.trigger_event("my_event", a=9, b=2)
    assert calls == [(9, 2)]


def test_event_manager_add_event_handler_filter_payload_default_is_false() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler)
    assert not registered_subscription(manager).filter_payload


def test_event_manager_add_event_handler_condition_default_is_none() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler)
    assert registered_subscription(manager).condition is None


def test_event_manager_add_event_handler_options_reach_subscription() -> None:
    manager = EventManager()
    condition = PeriodicCondition(freq=2)
    subscription = manager.add_event_handler(
        "my_event", hello_handler, once=True, condition=condition, filter_payload=True
    )
    assert {
        "event": subscription.event,
        "handler": subscription.handler,
        "once": subscription.once,
        "condition": subscription.condition,
        "filter_payload": subscription.filter_payload,
    } == {
        "event": "my_event",
        "handler": hello_handler,
        "once": True,
        "condition": condition,
        "filter_payload": True,
    }


def test_event_manager_on_and_add_event_handler_give_same_options() -> None:
    manager = EventManager()
    condition = PeriodicCondition(freq=2)
    manager.on("my_event", once=True, condition=condition, filter_payload=True)(hello_handler)
    subscription = manager.add_event_handler(
        "my_event", hello_handler, once=True, condition=condition, filter_payload=True
    )
    first = registered_subscription(manager)
    assert (first.handler, first.once, first.condition, first.filter_payload) == (
        subscription.handler,
        subscription.once,
        subscription.condition,
        subscription.filter_payload,
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
    manager.add_event_handler("my_event", payload_handler)
    manager.trigger_event("my_event", epoch=3, loss=0.5)
    assert payload_handler.kwargs == {"epoch": 3, "loss": 0.5}


def test_event_manager_trigger_event_payload_all_handlers() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler)
    manager.add_event_handler("my_event", functools.partial(payload_handler, 1))
    manager.trigger_event("my_event", epoch=3)
    assert payload_handler.call_count == 2


def test_event_manager_trigger_event_without_payload() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler)
    manager.trigger_event("my_event")
    assert payload_handler.kwargs == {}


def test_event_manager_trigger_event_payload_not_accepted_by_handler() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler)
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


class CallableRecorder:
    r"""Implements a callable object that records the payload."""

    def __init__(self, calls: list[dict[str, Any]]) -> None:
        self._calls = calls

    def __call__(self, **payload: Any) -> None:
        self._calls.append(payload)


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
    event_manager.trigger_event("my_event", value=1)
    assert calls == [{"value": 1}]


def test_event_manager_trigger_event_payload_with_event_and_self_keys() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler)
    manager.trigger_event("my_event", event="batch_end", self=1)
    assert payload_handler.kwargs == {"event": "batch_end", "self": 1}


async def test_event_manager_atrigger_event_payload_with_event_and_self_keys() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler)
    await manager.atrigger_event("my_event", event="batch_end", self=1)
    assert payload_handler.kwargs == {"event": "batch_end", "self": 1}


def test_event_manager_trigger_event_once_payload_with_self_key() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler, once=True)
    manager.trigger_event("my_event", self=1)
    assert payload_handler.kwargs == {"self": 1}


async def test_event_manager_atrigger_event_once_payload_with_self_key() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler, once=True)
    await manager.atrigger_event("my_event", self=1)
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


####################################
#     Tests for _is_registered     #
####################################


def test_event_manager_is_registered_true() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", print)
    assert manager._is_registered(subscription)


def test_event_manager_is_registered_false_after_remove() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", print)
    subscription.remove()
    assert not manager._is_registered(subscription)


def test_event_manager_is_registered_false_never_registered() -> None:
    manager = EventManager()
    assert not manager._is_registered(Subscription(manager, "my_event", print))


def test_event_manager_is_registered_false_for_other_manager() -> None:
    subscription = EventManager().add_event_handler("my_event", print)
    assert not EventManager()._is_registered(subscription)


def test_event_manager_is_registered_false_when_other_event_has_registrations() -> None:
    manager = EventManager()
    manager.add_event_handler("my_other_event", print)
    assert not manager._is_registered(Subscription(manager, "my_event", print))


def test_event_manager_is_registered_does_not_create_event() -> None:
    manager = EventManager()
    manager._is_registered(Subscription(manager, "my_event", print))
    assert "my_event" not in manager


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


def test_event_manager_on_filter_payload_passes_accepted_keys_only() -> None:
    manager = EventManager()
    epochs: list[int] = []

    @manager.on("my_event", filter_payload=True)
    def log_epoch(epoch: int) -> None:
        epochs.append(epoch)

    manager.trigger_event("my_event", epoch=3, loss=0.5)
    assert epochs == [3]


def test_event_manager_on_filter_payload_default_is_false() -> None:
    manager = EventManager()
    manager.on("my_event")(hello_handler)
    assert not registered_subscription(manager).filter_payload


def test_event_manager_on_filter_payload_reaches_subscription() -> None:
    manager = EventManager()
    manager.on("my_event", filter_payload=True)(hello_handler)
    assert registered_subscription(manager).filter_payload


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


def test_event_manager_on_condition_returns_function_unchanged() -> None:
    manager = EventManager()
    assert manager.on("my_event", condition=lambda: True)(hello_handler) is hello_handler


def test_event_manager_on_once_with_options() -> None:
    manager = EventManager()
    manager.on("my_event", once=True, condition=lambda: True, filter_payload=True)(hello_handler)
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


def test_event_manager_trigger_event_filter_payload_shares_event() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler, filter_payload=True)
    manager.add_event_handler("my_event", payload_handler)
    manager.trigger_event("my_event", epoch=3, loss=0.5)
    assert payload_handler.kwargs == {"epoch": 3, "loss": 0.5}


def test_event_manager_trigger_event_filter_payload_does_not_fail_other_handler() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler, filter_payload=True)
    manager.trigger_event("my_event", epoch=3)
    assert hello_handler.call_count == 1


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


def test_subscription_filter_payload_default() -> None:
    assert not Subscription(EventManager(), "my_event", print).filter_payload


def test_subscription_filter_payload_true() -> None:
    assert Subscription(EventManager(), "my_event", print, filter_payload=True).filter_payload


def test_subscription_call_returns_handler_result() -> None:
    assert Subscription(EventManager(), "my_event", lambda **payload: payload)._call({"a": 1}) == {
        "a": 1
    }


def test_subscription_call_condition_false_returns_none() -> None:
    subscription = Subscription(EventManager(), "my_event", lambda: 1, condition=lambda: False)
    assert subscription._call({}) is None


def test_subscription_call_condition_false_does_not_call_handler() -> None:
    subscription = Subscription(EventManager(), "my_event", hello_handler, condition=lambda: False)
    subscription._call({})
    assert hello_handler.call_count == 0


def test_subscription_call_condition_true_calls_handler() -> None:
    subscription = Subscription(EventManager(), "my_event", lambda: 1, condition=lambda: True)
    assert subscription._call({}) == 1


def test_subscription_call_condition_is_called_once() -> None:
    condition = Mock(return_value=True)
    Subscription(EventManager(), "my_event", hello_handler, condition=condition)._call({})
    assert condition.call_count == 1


def test_subscription_options_are_keyword_only() -> None:
    args: list[Any] = [EventManager(), "my_event", print, True]
    with pytest.raises(TypeError, match=r"positional arguments"):
        Subscription(*args)


def test_subscription_call_once_removes_registration() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", hello_handler, once=True)
    subscription._call({})
    assert not subscription.active


def test_subscription_call_once_calls_handler() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", lambda: 1, once=True)
    assert manager.get_subscriptions("my_event")[0]._call({}) == 1


def test_subscription_call_once_already_removed_returns_none() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", lambda: 1, once=True)
    subscription.remove()
    assert subscription._call({}) is None


def test_subscription_call_once_already_removed_does_not_call_handler() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", hello_handler, once=True)
    subscription.remove()
    subscription._call({})
    assert hello_handler.call_count == 0


def test_subscription_call_not_once_keeps_registration() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", hello_handler)
    subscription._call({})
    assert subscription.active


def test_subscription_call_does_not_filter_by_default() -> None:
    subscription = Subscription(EventManager(), "my_event", lambda **payload: payload)
    assert subscription._call({"a": 1, "b": 2}) == {"a": 1, "b": 2}


def test_subscription_call_filters_payload() -> None:
    def handler(a: int) -> int:
        return a

    subscription = Subscription(EventManager(), "my_event", handler, filter_payload=True)
    assert subscription._call({"a": 1, "b": 2}) == 1


def test_subscription_call_filter_does_not_mutate_payload() -> None:
    payload: dict[str, object] = {"a": 1, "b": 2}
    Subscription(EventManager(), "my_event", lambda a: a, filter_payload=True)._call(payload)
    assert payload == {"a": 1, "b": 2}


def test_subscription_call_filter_keeps_all_keys_for_var_keyword() -> None:
    subscription = Subscription(
        EventManager(), "my_event", lambda **payload: payload, filter_payload=True
    )
    assert subscription._call({"a": 1, "b": 2}) == {"a": 1, "b": 2}


def test_subscription_call_filter_keeps_all_keys_for_uninspectable_handler() -> None:
    calls: list[dict[str, Any]] = []
    handler = UninspectableCallable(calls)
    Subscription(EventManager(), "my_event", handler, filter_payload=True)._call({"a": 1, "b": 2})
    assert calls == [{"a": 1, "b": 2}]


def test_subscription_call_condition_combinator_short_circuit() -> None:
    first = Mock(return_value=False)
    periodic = PeriodicCondition(2)
    subscription = Subscription(
        EventManager(),
        "my_event",
        hello_handler,
        condition=lambda: first() and periodic(),
    )
    for _ in range(3):
        subscription._call({})
    assert periodic._step == 0


def test_subscription_call_condition_combinator_evaluates_all() -> None:
    periodic = PeriodicCondition(2)
    subscription = Subscription(
        EventManager(),
        "my_event",
        hello_handler,
        condition=lambda: all([False, periodic()]),
    )
    for _ in range(3):
        subscription._call({})
    assert periodic._step == 3


########################################
#     Tests for _accepted_keywords     #
########################################


@trace
def epoch_handler(epoch: int) -> None:
    logger.info("epoch %s", epoch)


@trace
def keyword_only_handler(*, loss: float) -> None:
    logger.info("loss %s", loss)


def named_handler(first_name: str, last_name: str) -> None:
    r"""Implements a handler with two named arguments."""
    logger.info("Hello. I am %s %s", first_name, last_name)


def positional_only_handler(epoch: int, /) -> None:
    logger.info("epoch %s", epoch)


def kwargs_handler(**kwargs: Any) -> None:
    logger.info("Kwargs: %s", kwargs)


class UninspectableCallable:
    r"""Implements a callable whose signature cannot be inspected."""

    __signature__ = 1

    def __init__(self, calls: list[dict[str, Any]]) -> None:
        self._calls = calls

    def __call__(self, **kwargs: Any) -> None:
        self._calls.append(kwargs)


def test_accepted_keywords_uninspectable() -> None:
    assert _accepted_keywords(UninspectableCallable([])) is None


def test_accepted_keywords_var_keyword() -> None:
    assert _accepted_keywords(kwargs_handler) is None


def test_accepted_keywords_positional_or_keyword() -> None:
    assert _accepted_keywords(epoch_handler) == frozenset({"epoch"})


def test_accepted_keywords_keyword_only() -> None:
    assert _accepted_keywords(keyword_only_handler) == frozenset({"loss"})


def test_accepted_keywords_positional_only() -> None:
    assert _accepted_keywords(positional_only_handler) == frozenset()


def test_accepted_keywords_no_parameter() -> None:
    assert _accepted_keywords(hello_handler) == frozenset()


def test_accepted_keywords_mixed() -> None:
    assert _accepted_keywords(named_handler) == frozenset({"first_name", "last_name"})


def test_accepted_keywords_partial_binding_positional_argument() -> None:
    assert _accepted_keywords(functools.partial(named_handler, "John")) == frozenset({"last_name"})


def test_accepted_keywords_partial_binding_keyword_argument() -> None:
    assert _accepted_keywords(functools.partial(named_handler, last_name="Doe")) == frozenset(
        {"first_name", "last_name"}
    )


####################################################
#     Tests for filter_payload in the manager      #
####################################################


def test_event_manager_filter_payload_false_raises_for_unknown_key() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", epoch_handler)
    with pytest.raises(TypeError, match=r"unexpected keyword argument 'loss'"):
        manager.trigger_event("my_event", epoch=3, loss=0.5)


def test_event_manager_filter_payload_keeps_accepted_keys() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", epoch_handler, filter_payload=True)
    manager.trigger_event("my_event", epoch=3, loss=0.5)
    assert epoch_handler.kwargs == {"epoch": 3}


def test_event_manager_filter_payload_no_parameter() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler, filter_payload=True)
    manager.trigger_event("my_event", epoch=3)
    assert hello_handler.call_count == 1


def test_event_manager_filter_payload_keyword_only_parameter() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", keyword_only_handler, filter_payload=True)
    manager.trigger_event("my_event", epoch=3, loss=0.5)
    assert keyword_only_handler.kwargs == {"loss": 0.5}


def test_event_manager_filter_payload_missing_key_still_raises() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", epoch_handler, filter_payload=True)
    with pytest.raises(TypeError, match=r"missing 1 required positional argument: 'epoch'"):
        manager.trigger_event("my_event", loss=0.5)


def test_event_manager_filter_payload_positional_only_not_passed() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", positional_only_handler, filter_payload=True)
    with pytest.raises(TypeError, match=r"missing 1 required positional argument"):
        manager.trigger_event("my_event", epoch=3)


def test_subscription_active_after_add() -> None:
    assert EventManager().add_event_handler("my_event", print).active


def test_subscription_active_never_registered() -> None:
    assert not Subscription(EventManager(), "my_event", print).active


def test_subscription_active_never_registered_stays_inactive_after_remove() -> None:
    subscription = Subscription(EventManager(), "my_event", print)
    subscription.remove()
    assert not subscription.active


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
        contextlib.suppress(RuntimeError),
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

    with pytest.raises(TypeError, match=r"returned an awaitable; use atrigger_event"):
        _check_not_awaitable(coroutine_handler(), coroutine_handler)


def test_check_not_awaitable_closes_coroutine() -> None:
    async def coroutine_handler() -> None:
        r"""Implement a coroutine handler."""

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
