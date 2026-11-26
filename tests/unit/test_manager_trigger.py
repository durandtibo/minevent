from __future__ import annotations

import dataclasses
import functools
from typing import Any
from unittest.mock import create_autospec

import pytest

from minevent import (
    EventManager,
    PeriodicCondition,
    Subscription,
)
from tests.unit.handlers import (
    AwaitableResult,
    CallableRecorder,
    CustomCondition,
    UnnameableCallable,
    condition_returning_a_coroutine,
    fail,
    has_payload,
    hello_handler,
    noop_handler,
    read_epoch,
)
from tests.unit.utils import INVALID_EVENTS, raised


def add_hello_handler_when_triggered(manager: EventManager) -> None:
    r"""Register a handler that adds ``hello_handler`` to
    ``my_event``."""
    manager.add_event_handler(
        "my_event", lambda: manager.add_event_handler("my_event", hello_handler)
    )


async def async_handler_with_argument(secret: str) -> None:
    r"""Implement a coroutine handler that has an argument."""


def coroutine_with_argument(secret: str) -> object:
    r"""Implement a synchronous handler that returns a coroutine."""
    return async_handler_with_argument(secret)


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


###################################
#     Tests for trigger_event     #
###################################


def test_event_manager_trigger_event_2_times() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", hello_handler)
    event_manager.trigger_event("my_event")
    event_manager.trigger_event("my_event")
    assert hello_handler.call_count == 2


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


@pytest.mark.parametrize("event", INVALID_EVENTS)
def test_event_manager_trigger_event_event_must_be_str(event: Any) -> None:
    with pytest.raises(TypeError, match=r"event must be a str"):
        EventManager().trigger_event(event)


def test_event_manager_trigger_event_handler_retriggering_its_event_raises_recursion_error() -> (
    None
):
    manager = EventManager()
    manager.add_event_handler("my_event", lambda: manager.trigger_event("my_event"))
    with pytest.raises(RecursionError, match=r"maximum recursion depth exceeded"):
        manager.trigger_event("my_event")


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


def test_event_manager_trigger_event_condition_with_parameter_and_handler_without() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler, condition=has_payload)
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 0


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


############################################
#     Tests for an awaitable condition     #
############################################


@pytest.mark.parametrize("condition", [AwaitableResult, condition_returning_a_coroutine])
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


#################################################
#     Tests for the notes of the exceptions     #
#################################################


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


def test_event_manager_trigger_event_coroutine_function_names_function_of_partial() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", functools.partial(async_handler_with_argument, "secret"))
    with pytest.raises(TypeError, match=r"^async_handler_with_argument is a coroutine function; "):
        manager.trigger_event("my_event")


def test_event_manager_trigger_event_hidden_coroutine_names_function_of_partial() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", functools.partial(coroutine_with_argument, "secret"))
    with pytest.raises(
        TypeError, match=r"^coroutine_with_argument returned an awaitable; use atrigger_event"
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


def test_event_manager_trigger_event_note_long_event() -> None:
    manager = EventManager()
    event = "a" * 100 + "x" * 100_000 + "b" * 100
    manager.add_event_handler(event, fail)
    assert raised(manager.trigger_event, event).__notes__ == [
        (
            "raised by fail while handling the event "
            "'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            "aaaaaaaaaaaaaaaaaa...bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
            "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'"
        )
    ]


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


def test_event_manager_trigger_event_keeps_error_of_unnameable_handler() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", UnnameableCallable())
    with pytest.raises(ValueError, match=r"boom") as exc_info:
        manager.trigger_event("my_event")
    assert exc_info.value.__notes__ == [
        "raised by UnnameableCallable while handling the event 'my_event'"
    ]


def test_event_manager_trigger_event_keeps_error_of_unnameable_condition() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", noop_handler, condition=UnnameableCallable())
    with pytest.raises(ValueError, match=r"boom") as exc_info:
        manager.trigger_event("my_event")
    assert exc_info.value.__notes__ == [
        (
            "raised by the condition UnnameableCallable of noop_handler "
            "while handling the event 'my_event'"
        )
    ]


@pytest.mark.parametrize("option", ["handler", "condition"])
def test_event_manager_trigger_event_frozen_exception_is_unchanged(option: str) -> None:
    error = FrozenError()
    raising = create_autospec(noop_handler, side_effect=error)
    manager = EventManager()
    options: dict[str, Any] = {"handler": noop_handler, option: raising}
    manager.add_event_handler("my_event", **options)
    assert raised(manager.trigger_event, "my_event") is error
