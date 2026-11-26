from __future__ import annotations

import functools
import logging
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock, create_autospec

import pytest

from minevent import (
    Context,
    EventManager,
    PeriodicCondition,
    Subscription,
)
from tests.unit.handlers import (
    AsyncConditionMethod,
    AsyncConditionObject,
    AsyncGeneratorObject,
    CallableRecorder,
    GeneratorObject,
    ModelStandIn,
    async_condition,
    generator_handler,
    hello_handler,
    named_handler,
    noop_handler,
    payload_handler,
    read_epoch,
    requires_lazy_annotations,
    unresolved_function,
)
from tests.unit.utils import INVALID_EVENTS, trace

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


logger = logging.getLogger(__name__)


EVENTS = ("my_event", "my_other_event")


def registered_subscription(manager: EventManager) -> Subscription:
    r"""Return the first ``Subscription`` registered to ``my_event``."""
    return manager.get_subscriptions("my_event")[0]


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


INVALID_HANDLERS = [None, "handler", 5, EventManager()]


def no_parameter_handler() -> None:
    r"""Implement a handler without parameter."""


def optional_context_handler(context: Context | None = None) -> None:
    r"""Implement a handler with an optional context."""
    logger.info("Payload: %s", context)


class BadReprValue:
    r"""Implement a value that is not callable and whose ``repr``
    raises."""

    def __repr__(self) -> str:
        msg = "repr failed"
        raise RuntimeError(msg)


#######################################
#     Tests for add_event_handler     #
#######################################


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


@pytest.mark.parametrize("handler", INVALID_HANDLERS)
def test_event_manager_add_event_handler_handler_must_be_callable(handler: Any) -> None:
    with pytest.raises(TypeError, match=r"handler must be callable"):
        EventManager().add_event_handler("my_event", handler)


@pytest.mark.parametrize("handler", INVALID_HANDLERS)
def test_event_manager_add_event_handler_invalid_handler_is_not_registered(handler: Any) -> None:
    manager = EventManager()
    with pytest.raises(TypeError, match=r"handler must be callable"):
        manager.add_event_handler("my_event", handler)
    assert manager.events == []


@pytest.mark.parametrize("option", ["handler", "condition"])
def test_event_manager_add_event_handler_not_callable_repr_raises(option: str) -> None:
    manager = EventManager()
    options: dict[str, Any] = {"handler": noop_handler, option: BadReprValue()}
    with pytest.raises(TypeError, match=rf"^{option} must be callable, but got <BadReprValue "):
        manager.add_event_handler("my_event", **options)
    assert manager.events == []


@pytest.mark.parametrize("option", ["handler", "condition"])
def test_event_manager_add_event_handler_not_callable_long_value(option: str) -> None:
    options: dict[str, Any] = {"handler": noop_handler, option: list(range(100))}
    with pytest.raises(
        TypeError,
        match=rf"^{option} must be callable, but got \[0, 1, 2, 3, 4, 5, \.\.\.\]$",
    ):
        EventManager().add_event_handler("my_event", **options)


def test_event_manager_add_event_handler_condition_must_be_callable() -> None:
    condition: Any = 5
    with pytest.raises(TypeError, match=r"condition must be callable"):
        EventManager().add_event_handler("my_event", hello_handler, condition=condition)


def test_event_manager_add_event_handler_invalid_condition_is_not_registered() -> None:
    manager = EventManager()
    condition: Any = 5
    with pytest.raises(TypeError, match=r"condition must be callable"):
        manager.add_event_handler("my_event", hello_handler, condition=condition)
    assert manager.events == []


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
    manager.add_event_handler("my_event", hello_handler, condition=lambda _: False)
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 0


def test_event_manager_add_event_handler_condition_true_runs_handler() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler, condition=lambda _: True)
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


@pytest.mark.parametrize("event", INVALID_EVENTS)
def test_event_manager_add_event_handler_event_must_be_str(event: Any) -> None:
    with pytest.raises(TypeError, match=r"event must be a str"):
        EventManager().add_event_handler(event, hello_handler)


########################
#     Tests for on     #
########################


@pytest.mark.parametrize("handler", INVALID_HANDLERS)
def test_event_manager_on_handler_must_be_callable(handler: Any) -> None:
    with pytest.raises(TypeError, match=r"handler must be callable"):
        EventManager().on("my_event")(handler)


def test_event_manager_on_invalid_handler_is_not_registered() -> None:
    manager = EventManager()
    handler: Any = 5
    with pytest.raises(TypeError, match=r"handler must be callable"):
        manager.on("my_event")(handler)
    assert manager.events == []


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


def test_event_manager_on_registers_function() -> None:
    manager = EventManager()

    @manager.on("my_event")
    def handler(_: Context) -> None:
        hello_handler(Context())

    manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


def test_event_manager_on_returns_function_unchanged() -> None:
    manager = EventManager()

    def handler(_: Context) -> None:
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
    manager.on("my_event", condition=lambda _: False)(hello_handler)
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 0


def test_event_manager_on_condition_true_runs_handler() -> None:
    manager = EventManager()
    manager.on("my_event", condition=lambda _: True)(hello_handler)
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


def test_event_manager_on_condition_evaluated_before_handler() -> None:
    manager = EventManager()
    calls: list[str] = []

    def condition(_: Context) -> bool:
        calls.append("condition")
        return True

    @manager.on("my_event", condition=condition)
    def handler(_: Context) -> None:
        calls.append("handler")

    manager.trigger_event("my_event")
    assert calls == ["condition", "handler"]


def test_event_manager_on_condition_reads_the_payload() -> None:
    manager = EventManager()
    manager.on("my_event", condition=lambda context: context["go"])(hello_handler)
    manager.trigger_event("my_event", {"go": True})
    manager.trigger_event("my_event", {"go": False})
    assert hello_handler.call_count == 1


def test_event_manager_on_condition_returns_function_unchanged() -> None:
    manager = EventManager()
    assert manager.on("my_event", condition=lambda _: True)(hello_handler) is hello_handler


def test_event_manager_on_once_with_options() -> None:
    manager = EventManager()
    manager.on("my_event", once=True, condition=lambda _: True)(hello_handler)
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


######################################################
#     Tests for the signatures of a registration     #
######################################################


@requires_lazy_annotations
def test_event_manager_add_event_handler_unresolved_annotation(tmp_path: Path) -> None:
    handler = unresolved_function(tmp_path, "unresolved_return")
    subscription = EventManager().add_event_handler("my_event", handler)
    assert subscription.active


@requires_lazy_annotations
def test_event_manager_add_event_handler_condition_unresolved_annotation(tmp_path: Path) -> None:
    condition = unresolved_function(tmp_path, "unresolved_return")
    subscription = EventManager().add_event_handler("my_event", noop_handler, condition=condition)
    assert subscription.active


@pytest.mark.parametrize("handler", [print, named_handler, generator_handler])
def test_event_manager_add_event_handler_rejected_handler_leaves_manager_unchanged(
    handler: Callable[..., object],
) -> None:
    manager = EventManager()
    with pytest.raises(TypeError, match=r"^handler "):
        manager.add_event_handler("my_event", handler)
    assert manager.events == []


@pytest.mark.parametrize("condition", [Mock(), named_handler, generator_handler])
def test_event_manager_add_event_handler_rejected_condition_leaves_manager_unchanged(
    condition: Any,
) -> None:
    manager = EventManager()
    with pytest.raises(TypeError, match=r"^condition "):
        manager.add_event_handler("my_event", noop_handler, condition=condition)
    assert manager.events == []


def test_event_manager_add_event_handler_async_callable_condition() -> None:
    manager = EventManager()
    condition: Any = AsyncConditionObject()
    with pytest.raises(
        TypeError, match=r"^condition must be synchronous, but got AsyncConditionObject$"
    ):
        manager.add_event_handler("my_event", noop_handler, condition=condition)
    assert manager.events == []


@pytest.mark.parametrize("handler", [GeneratorObject(), AsyncGeneratorObject()])
def test_event_manager_add_event_handler_generator_object(handler: Any) -> None:
    manager = EventManager()
    with pytest.raises(TypeError, match=r"^handler must not be a generator function, but got "):
        manager.add_event_handler("my_event", handler)
    assert manager.events == []


@pytest.mark.parametrize(
    "condition",
    [
        async_condition,
        AsyncConditionMethod().check,
        functools.partial(async_condition),
        AsyncConditionObject(),
        functools.partial(AsyncConditionObject()),
    ],
)
def test_event_manager_add_event_handler_async_condition(condition: Any) -> None:
    manager = EventManager()
    with pytest.raises(TypeError, match=r"^condition must be synchronous, but got "):
        manager.add_event_handler("my_event", noop_handler, condition=condition)
    assert manager.events == []


def test_event_manager_on_async_condition() -> None:
    manager = EventManager()
    condition: Any = async_condition
    decorator = manager.on("my_event", condition=condition)
    with pytest.raises(TypeError, match=r"^condition must be synchronous, but got async_condition"):
        decorator(noop_handler)
    assert manager.events == []


def test_event_manager_on_rejected_signature() -> None:
    manager = EventManager()
    decorator = manager.on("my_event")
    handler: Any = named_handler
    with pytest.raises(
        TypeError,
        match=r"^handler named_handler must take the context as its only required argument",
    ):
        decorator(handler)
    assert manager.events == []


def test_event_manager_on_rejected_condition_signature() -> None:
    manager = EventManager()
    decorator = manager.on("my_event", condition=Mock())
    with pytest.raises(
        TypeError, match=r"^condition Mock must take the context as its only required argument"
    ):
        decorator(noop_handler)
    assert manager.events == []


@pytest.mark.parametrize(
    "handler",
    [no_parameter_handler, ModelStandIn().train, lambda i=0: i, optional_context_handler],
    ids=["no-parameter", "bound-method", "lambda-default", "optional-context"],
)
def test_event_manager_add_event_handler_handler_without_required_parameter(handler: Any) -> None:
    manager = EventManager()
    with pytest.raises(TypeError, match=r"^handler .+ must take the context as its only required"):
        manager.add_event_handler("my_event", handler)
    assert manager.events == []


@pytest.mark.parametrize(
    "condition",
    [no_parameter_handler, lambda flag=False: flag, optional_context_handler],
    ids=["no-parameter", "lambda-default", "optional-context"],
)
def test_event_manager_add_event_handler_condition_without_required_parameter(
    condition: Any,
) -> None:
    manager = EventManager()
    with pytest.raises(TypeError, match=r"^condition .+ must take the context as its only"):
        manager.add_event_handler("my_event", noop_handler, condition=condition)
    assert manager.events == []


def test_event_manager_trigger_event_lambda_keeps_its_saved_value() -> None:
    values: list[object] = []
    manager = EventManager()
    manager.add_event_handler("my_event", lambda _, i=0: values.append(i))
    manager.add_event_handler("my_event", lambda _, i=1: values.append(i))
    manager.trigger_event("my_event", {"epoch": 3})
    assert values == [0, 1]


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
