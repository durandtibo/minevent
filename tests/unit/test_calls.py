from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import sys
from collections.abc import Awaitable
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, Mock, create_autospec

import pytest

from minevent import Context
from minevent.calls import add_error_note, describe, needs_context, reject_awaitable
from tests.unit.handlers import (
    BadReprCallable,
    CallableRecorder,
    CustomCondition,
    ModelStandIn,
    fail,
    generator_handler,
    hello_handler,
    named_handler,
    noop_handler,
    payload_handler,
    read_epoch,
    requires_lazy_annotations,
    unresolved_function,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterator
    from pathlib import Path


logger = logging.getLogger(__name__)


class CallableObject:
    def __call__(self) -> None:
        r"""Implement a callable without a name."""


def positional_handler(context: Context) -> None:
    logger.info("context %s", context)


def positional_only_handler(context: Context, /) -> None:
    logger.info("context %s", context)


def default_handler(context: Context | None = None) -> None:
    logger.info("context %s", context)


def context_then_default_handler(context: Context, verbose: bool = False) -> None:
    logger.info("context %s %s", context, verbose)


def context_then_keyword_default_handler(context: Context, *, verbose: bool = False) -> None:
    logger.info("context %s %s", context, verbose)


def keyword_default_handler(*, value: int = 1) -> None:
    logger.info("value %s", value)


def keyword_only_handler(*, loss: float) -> None:
    logger.info("loss %s", loss)


def context_and_keyword_only_handler(context: Context, *, loss: float) -> None:
    logger.info("context %s %s", context, loss)


def var_positional_handler(*args: object) -> None:
    logger.info("Args: %s", args)


def var_keyword_handler(**kwargs: object) -> None:
    logger.info("Kwargs: %s", kwargs)


def var_handler(*args: object, **kwargs: object) -> None:
    logger.info("Args: %s %s", args, kwargs)


def context_and_var_positional_handler(context: Context, *args: object) -> None:
    logger.info("context %s %s", context, args)


async def async_no_parameter_handler() -> None:
    r"""Implement a coroutine handler without parameter."""


async def async_context_handler(context: Context) -> None:
    r"""Implement a coroutine handler that receives the context."""


def generator_context_handler(context: Context) -> Iterator[Context]:
    r"""Implement a generator handler that receives the context."""
    yield context


async def async_generator_handler() -> AsyncIterator[None]:
    r"""Implement an async generator handler."""
    yield


@functools.wraps(positional_handler)
def wrapping_handler(*args: Any) -> None:
    r"""Implement a decorator of ``positional_handler``."""
    positional_handler(*args)


class UninspectableCallable:
    r"""Implements a callable whose signature cannot be inspected."""

    __signature__ = 1

    def __call__(self, context: Context) -> None:
        r"""Implement a handler."""


###################################
#     Tests for needs_context     #
###################################


@pytest.mark.parametrize(
    "func",
    [
        hello_handler,
        ModelStandIn().train,
        lambda i=1: i,
        keyword_default_handler,
        functools.partial(keyword_default_handler, value=2),
        default_handler,
        functools.partial(positional_handler, Context()),
        functools.partial(positional_handler, context=Context()),
        CustomCondition(),
        ModelStandIn,
        async_no_parameter_handler,
        create_autospec(noop_handler),
    ],
)
def test_needs_context_no_argument(func: Callable[..., object]) -> None:
    assert not needs_context(func, "handler")


@pytest.mark.parametrize(
    "func",
    [
        positional_handler,
        positional_only_handler,
        context_then_default_handler,
        context_then_keyword_default_handler,
        lambda context: context,
        lambda context, i=1: (context, i),
        CallableRecorder([]),
        CallableRecorder,
        functools.partial(named_handler, "John"),
        async_context_handler,
        wrapping_handler,
        create_autospec(read_epoch),
    ],
)
def test_needs_context_one_argument(func: Callable[..., object]) -> None:
    assert needs_context(func, "handler")


REJECTED_SIGNATURES = [
    var_positional_handler,
    var_keyword_handler,
    var_handler,
    context_and_var_positional_handler,
    print,
    functools.partial(print, "Hello!"),
    Mock(),
    AsyncMock(),
    max,
    dict.update,
    UninspectableCallable(),
    named_handler,
    keyword_only_handler,
    context_and_keyword_only_handler,
    functools.partial(named_handler, first_name="John"),
]


@pytest.mark.parametrize("func", REJECTED_SIGNATURES)
def test_needs_context_rejected_signature(func: Callable[..., object]) -> None:
    with pytest.raises(TypeError, match=r"^handler .+ must need no argument or only the context"):
        needs_context(func, "handler")


@pytest.mark.parametrize(
    "func",
    [
        generator_handler,
        generator_context_handler,
        async_generator_handler,
        functools.partial(generator_handler),
        ModelStandIn().generate,
    ],
)
def test_needs_context_generator_function(func: Callable[..., object]) -> None:
    with pytest.raises(TypeError, match=r"^handler must not be a generator function, but got"):
        needs_context(func, "handler")


def test_needs_context_error_names_the_argument_and_the_function() -> None:
    with pytest.raises(
        TypeError,
        match=r"^condition named_handler must need no argument or only the context; "
        r"wrap it in a function or a lambda$",
    ):
        needs_context(named_handler, "condition")


def test_needs_context_generator_error_names_the_argument_and_the_function() -> None:
    with pytest.raises(
        TypeError,
        match=r"^condition must not be a generator function, but got generator_handler$",
    ):
        needs_context(generator_handler, "condition")


def test_needs_context_error_ignores_repr_of_bound_arguments() -> None:
    func = functools.partial(var_positional_handler, BadReprCallable())
    with pytest.raises(TypeError, match=r"^handler var_positional_handler must need"):
        needs_context(func, "handler")


def test_needs_context_uninspectable_error_has_the_cause() -> None:
    with pytest.raises(TypeError, match=r"must need no argument or only the context") as exc_info:
        needs_context(UninspectableCallable(), "handler")
    assert isinstance(exc_info.value.__cause__, TypeError)


@requires_lazy_annotations
def test_needs_context_unresolved_return_annotation(tmp_path: Path) -> None:
    assert not needs_context(unresolved_function(tmp_path, "no_parameter"), "handler")


@requires_lazy_annotations
def test_needs_context_unresolved_parameter_annotation(tmp_path: Path) -> None:
    assert needs_context(unresolved_function(tmp_path, "one_parameter"), "handler")


def test_needs_context_before_python_3_14(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "version_info", (3, 13, 0))
    assert needs_context(positional_handler, "handler")


##############################
#     Tests for describe     #
##############################


def test_describe_function() -> None:
    assert describe(fail) == "fail"


def test_describe_partial() -> None:
    assert describe(functools.partial(fail)) == "fail"


def test_describe_partial_with_arguments() -> None:
    assert describe(functools.partial(payload_handler, 1, k=2)) == "payload_handler"


def test_describe_nested_partial() -> None:
    assert describe(functools.partial(functools.partial(fail))) == "fail"


def test_describe_method() -> None:
    assert describe(CallableObject().__call__) == "CallableObject.__call__"


def test_describe_callable_object() -> None:
    assert describe(CallableObject()) == "CallableObject"


######################################
#     Tests for reject_awaitable     #
######################################


def test_reject_awaitable_none() -> None:
    assert reject_awaitable(None, "returned an awaitable") is None


@pytest.mark.parametrize("result", [True, False, 0, 1, "value", [1]])
def test_reject_awaitable_value(result: object) -> None:
    assert reject_awaitable(result, "returned an awaitable") is None


def test_reject_awaitable_coroutine_raises() -> None:
    with pytest.raises(TypeError, match=r"^func returned an awaitable$"):
        reject_awaitable(async_no_parameter_handler(), "func returned an awaitable")


def test_reject_awaitable_closes_the_coroutine() -> None:
    coroutine = async_no_parameter_handler()
    with pytest.raises(TypeError, match=r"returned an awaitable"):
        reject_awaitable(coroutine, "func returned an awaitable")
    assert inspect.getcoroutinestate(coroutine) == "CORO_CLOSED"


def test_reject_awaitable_awaitable_that_is_not_a_coroutine() -> None:
    with pytest.raises(TypeError, match=r"^func returned an awaitable$"):
        reject_awaitable(Mock(spec=Awaitable), "func returned an awaitable")


def test_reject_awaitable_does_not_close_a_future() -> None:
    future = Mock(spec=asyncio.Future)
    with pytest.raises(TypeError, match=r"returned an awaitable"):
        reject_awaitable(future, "func returned an awaitable")
    assert future.method_calls == []


####################################
#     Tests for add_error_note     #
####################################


def test_add_error_note() -> None:
    error = ValueError("boom")
    add_error_note(error, "my_event", fail)
    assert error.__notes__ == ["raised by fail while handling the event 'my_event'"]


def test_add_error_note_same_pair_twice_adds_one_note() -> None:
    error = ValueError("boom")
    handler = fail
    add_error_note(error, "my_event", handler)
    add_error_note(error, "my_event", handler)
    assert error.__notes__ == ["raised by fail while handling the event 'my_event'"]


def test_add_error_note_other_event_adds_note() -> None:
    error = ValueError("boom")
    handler = fail
    add_error_note(error, "my_event", handler)
    add_error_note(error, "my_other_event", handler)
    assert error.__notes__ == [
        "raised by fail while handling the event 'my_event'",
        "raised by fail while handling the event 'my_other_event'",
    ]


def test_add_error_note_other_handler_adds_note() -> None:
    error = ValueError("boom")
    add_error_note(error, "my_event", fail)
    add_error_note(error, "my_event", hello_handler)
    assert error.__notes__ == [
        "raised by fail while handling the event 'my_event'",
        "raised by hello_handler while handling the event 'my_event'",
    ]
