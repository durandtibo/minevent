from __future__ import annotations

import asyncio
import dataclasses
import functools
import inspect
import logging
import runpy
import sys
from collections.abc import Awaitable
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, Mock, create_autospec

import pytest

from minevent import Context, PeriodicCondition, calls
from minevent.calls import (
    add_error_note,
    describe,
    describe_event,
    has_kind,
    reject_awaitable,
    validate_signature,
)
from tests.unit.handlers import (
    AsyncConditionMethod,
    AsyncConditionObject,
    AsyncGeneratorObject,
    BadReprCallable,
    CallableRecorder,
    CustomCondition,
    GeneratorObject,
    ModelStandIn,
    UnnameableCallable,
    UnreadableClass,
    async_condition,
    condition_returning_a_coroutine,
    fail,
    generator_handler,
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
    def __call__(self, _: Context) -> None:
        r"""Implement a callable without a name."""


def positional_handler(context: Context) -> None:
    r"""Implement a handler with one positional parameter."""
    logger.info("context %s", context)


def positional_only_handler(context: Context, /) -> None:
    r"""Implement a handler with one positional-only parameter."""
    logger.info("context %s", context)


def default_handler(context: Context | None = None) -> None:
    r"""Implement a handler with an optional context."""
    logger.info("context %s", context)


def context_then_default_handler(context: Context, verbose: bool = False) -> None:
    r"""Implement a handler with the context then a default."""
    logger.info("context %s %s", context, verbose)


def context_then_keyword_default_handler(context: Context, *, verbose: bool = False) -> None:
    r"""Implement a handler with the context then a keyword default."""
    logger.info("context %s %s", context, verbose)


def keyword_default_handler(*, value: int = 1) -> None:
    r"""Implement a handler with a keyword-only default."""
    logger.info("value %s", value)


def keyword_only_handler(*, loss: float) -> None:
    r"""Implement a handler with a required keyword-only parameter."""
    logger.info("loss %s", loss)


def context_and_keyword_only_handler(context: Context, *, loss: float) -> None:
    r"""Implement a handler with the context and a keyword."""
    logger.info("context %s %s", context, loss)


def var_positional_handler(*args: object) -> None:
    r"""Implement a handler with ``*args``."""
    logger.info("Args: %s", args)


def var_keyword_handler(**kwargs: object) -> None:
    r"""Implement a handler with ``**kwargs``."""
    logger.info("Kwargs: %s", kwargs)


def var_handler(*args: object, **kwargs: object) -> None:
    r"""Implement a handler with ``*args`` and ``**kwargs``."""
    logger.info("Args: %s %s", args, kwargs)


def context_and_var_positional_handler(context: Context, *args: object) -> None:
    r"""Implement a handler with the context and ``*args``."""
    logger.info("context %s %s", context, args)


async def async_context_handler(context: Context) -> None:
    r"""Implement a coroutine handler that receives the context."""


def generator_context_handler(context: Context) -> Iterator[Context]:
    r"""Implement a generator handler that receives the context."""
    yield context


async def async_generator_handler(_: Context) -> AsyncIterator[None]:
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


########################################
#     Tests for validate_signature     #
########################################


def no_parameter_handler() -> None:
    r"""Implement a handler without parameter."""


async def async_no_parameter_handler() -> None:
    r"""Implement a coroutine handler without parameter."""


@pytest.mark.parametrize(
    "func",
    [
        positional_handler,
        positional_only_handler,
        noop_handler,
        context_then_default_handler,
        context_then_keyword_default_handler,
        lambda context: context,
        lambda _, i=1: i,
        CallableRecorder([]),
        CallableRecorder,
        CustomCondition(),
        PeriodicCondition(3),
        functools.partial(named_handler, "John"),
        async_context_handler,
        wrapping_handler,
        create_autospec(read_epoch),
    ],
)
def test_validate_signature_accepted(func: Callable[..., object]) -> None:
    assert validate_signature(func, "handler") is None


REJECTED_SIGNATURES = [
    # No parameter.
    no_parameter_handler,
    async_no_parameter_handler,
    ModelStandIn,
    create_autospec(no_parameter_handler),
    # Only parameters with a default.
    default_handler,
    keyword_default_handler,
    ModelStandIn().train,
    lambda i=1: i,
    functools.partial(positional_handler, context=Context()),
    # No parameter left.
    functools.partial(positional_handler, Context()),
    # ``*args`` and ``**kwargs``.
    var_positional_handler,
    var_keyword_handler,
    var_handler,
    context_and_var_positional_handler,
    print,
    functools.partial(print, "Hello!"),
    Mock(),
    AsyncMock(),
    # Cannot be inspected.
    max,
    dict.update,
    UninspectableCallable(),
    # Two required parameters, or a required keyword-only parameter.
    named_handler,
    keyword_only_handler,
    context_and_keyword_only_handler,
    functools.partial(named_handler, first_name="John"),
]


@pytest.mark.parametrize("func", REJECTED_SIGNATURES)
def test_validate_signature_rejected(func: Callable[..., object]) -> None:
    with pytest.raises(
        TypeError, match=r"^handler .+ must take the context as its only required argument"
    ):
        validate_signature(func, "handler")


def test_validate_signature_does_not_call_func() -> None:
    func = create_autospec(read_epoch)
    validate_signature(func, "handler")
    assert func.call_count == 0


@pytest.mark.parametrize(
    "func",
    [
        generator_handler,
        generator_context_handler,
        async_generator_handler,
        functools.partial(generator_handler),
        ModelStandIn().generate,
        GeneratorObject(),
        AsyncGeneratorObject(),
        functools.partial(GeneratorObject()),
    ],
)
def test_validate_signature_generator_function(func: Callable[..., object]) -> None:
    with pytest.raises(TypeError, match=r"^handler must not be a generator function, but got"):
        validate_signature(func, "handler")


def test_validate_signature_error_names_the_argument_and_the_function() -> None:
    with pytest.raises(
        TypeError,
        match=r"^condition named_handler must take the context as its only required argument; "
        r"wrap it in a function or a lambda$",
    ):
        validate_signature(named_handler, "condition")


def test_validate_signature_generator_error_names_the_argument_and_the_function() -> None:
    with pytest.raises(
        TypeError,
        match=r"^condition must not be a generator function, but got generator_handler$",
    ):
        validate_signature(generator_handler, "condition")


def test_validate_signature_error_ignores_repr_of_bound_arguments() -> None:
    func = functools.partial(var_positional_handler, BadReprCallable())
    with pytest.raises(TypeError, match=r"^handler var_positional_handler must take"):
        validate_signature(func, "handler")


def test_validate_signature_uninspectable_error_has_the_cause() -> None:
    with pytest.raises(
        TypeError, match=r"must take the context as its only required argument"
    ) as exc_info:
        validate_signature(UninspectableCallable(), "handler")
    assert isinstance(exc_info.value.__cause__, TypeError)


@requires_lazy_annotations
@pytest.mark.parametrize("name", ["unresolved_return", "unresolved_parameter"])
def test_validate_signature_unresolved_annotation(tmp_path: Path, name: str) -> None:
    assert validate_signature(unresolved_function(tmp_path, name), "handler") is None


def test_validate_signature_before_python_3_14(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "version_info", (3, 13, 0))
    assert validate_signature(positional_handler, "handler") is None


def test_calls_does_not_import_annotationlib_before_python_3_14(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "version_info", (3, 13, 0))
    # A fresh run of the module: ``minevent.calls`` is left as it is.
    assert "annotationlib" not in runpy.run_path(calls.__file__)


##############################
#     Tests for has_kind     #
##############################


@pytest.mark.parametrize(
    "func",
    [
        async_condition,
        AsyncConditionMethod().check,
        AsyncConditionObject(),
        functools.partial(async_condition),
        functools.partial(functools.partial(AsyncConditionObject())),
        AsyncMock(),
    ],
)
def test_has_kind_coroutine_function(func: Callable[..., object]) -> None:
    assert has_kind(func, inspect.iscoroutinefunction)


@pytest.mark.parametrize(
    "func",
    [
        noop_handler,
        ModelStandIn().train,
        functools.partial(noop_handler),
        CustomCondition(),
        AsyncConditionObject,
        condition_returning_a_coroutine,
        print,
        Mock(),
        generator_handler,
        async_generator_handler,
    ],
)
def test_has_kind_not_coroutine_function(func: Callable[..., object]) -> None:
    assert not has_kind(func, inspect.iscoroutinefunction)


@pytest.mark.parametrize(
    ("func", "predicate"),
    [
        (GeneratorObject(), inspect.isgeneratorfunction),
        (AsyncGeneratorObject(), inspect.isasyncgenfunction),
    ],
)
def test_has_kind_generator_object(
    func: Callable[..., object], predicate: Callable[[object], bool]
) -> None:
    assert has_kind(func, predicate)


@pytest.mark.parametrize("func", [GeneratorObject, noop_handler, AsyncGeneratorObject()])
def test_has_kind_not_generator_function(func: Callable[..., object]) -> None:
    assert not has_kind(func, inspect.isgeneratorfunction)


def mark_coroutine_function(func: Callable[..., object]) -> None:
    r"""Mark ``func`` as a coroutine function (Python 3.12+)."""
    if sys.version_info >= (3, 12):
        inspect.markcoroutinefunction(func)


@pytest.mark.skipif(sys.version_info < (3, 12), reason="markcoroutinefunction is new in 3.12")
def test_has_kind_marked_coroutine_function() -> None:
    def func(context: Context) -> object:
        return async_condition(context)

    mark_coroutine_function(func)
    assert has_kind(func, inspect.iscoroutinefunction)


@pytest.mark.skipif(sys.version_info < (3, 12), reason="markcoroutinefunction is new in 3.12")
def test_has_kind_marked_callable_object() -> None:
    func = CustomCondition()
    mark_coroutine_function(func)
    assert has_kind(func, inspect.iscoroutinefunction)


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


def test_describe_not_callable() -> None:
    assert describe(1) == "int"


def test_describe_qualname_raises() -> None:
    assert describe(UnnameableCallable()) == "UnnameableCallable"


def test_describe_partial_of_unnameable() -> None:
    assert describe(functools.partial(UnnameableCallable())) == "UnnameableCallable"


def test_describe_class_raises() -> None:
    assert describe(UnreadableClass()) == "UnreadableClass"


@pytest.mark.parametrize("name", [None, 1, b"name"])
def test_describe_qualname_not_a_str(name: object) -> None:
    handler = CallableObject()
    vars(handler)["__qualname__"] = name
    assert describe(handler) == "CallableObject"


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
        reject_awaitable(async_context_handler(Context()), "func returned an awaitable")


def test_reject_awaitable_closes_the_coroutine() -> None:
    coroutine = async_context_handler(Context())
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
#     Tests for describe_event     #
####################################


class Event(StrEnum):
    r"""Implement event names that are strings."""

    EPOCH_END = "epoch_end"


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        pytest.param("", "''", id="empty"),
        pytest.param("epoch_end", "'epoch_end'", id="short"),
        pytest.param("it's", '"it\'s"', id="quote"),
        pytest.param("a\nb", "'a\\nb'", id="newline"),
        pytest.param(Event.EPOCH_END, "<Event.EPOCH_END: 'epoch_end'>", id="str-enum"),
        pytest.param(
            "a" * 100 + "x" * 100_000 + "b" * 100,
            (
                "'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                "aaaaaaaaaaaaaaaaaa...bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
                "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'"
            ),
            id="long",
        ),
    ],
)
def test_describe_event(event: str, expected: str) -> None:
    assert describe_event(event) == expected


def test_describe_event_longest_name_is_not_shortened() -> None:
    # The repr has the 198 characters of the name and 2 quotes.
    event = "a" * 198
    assert describe_event(event) == repr(event)


@pytest.mark.parametrize("size", [199, 100_000])
def test_describe_event_length_is_bounded(size: int) -> None:
    assert len(describe_event("a" * size)) == 200


def test_describe_event_long_str_enum_member_is_bounded() -> None:
    class LongEvent(StrEnum):
        LONG = "a" * 1000

    assert len(describe_event(LongEvent.LONG)) == 200


def test_describe_event_repr_raises() -> None:
    class BadReprEvent(str):
        __slots__ = ()

        def __repr__(self) -> str:
            msg = "repr failed"
            raise RuntimeError(msg)

    assert describe_event(BadReprEvent("my_event")).startswith("<BadReprEvent instance at ")


####################################
#     Tests for add_error_note     #
####################################


@dataclasses.dataclass(frozen=True)
class FrozenError(Exception):
    r"""Implement an exception that forbids new attributes."""

    code: int = 1


def test_add_error_note() -> None:
    error = ValueError("boom")
    add_error_note(error, "fail", "my_event")
    assert error.__notes__ == ["raised by fail while handling the event 'my_event'"]


def test_add_error_note_returns_none() -> None:
    assert add_error_note(ValueError("boom"), "fail", "my_event") is None


def test_add_error_note_source_is_kept_as_given() -> None:
    error = ValueError("boom")
    add_error_note(error, "the condition is_late of log_epoch", "epoch_end")
    assert error.__notes__ == [
        "raised by the condition is_late of log_epoch while handling the event 'epoch_end'"
    ]


def test_add_error_note_empty_event() -> None:
    error = ValueError("boom")
    add_error_note(error, "fail", "")
    assert error.__notes__ == ["raised by fail while handling the event ''"]


def test_add_error_note_same_note_twice_adds_one_note() -> None:
    error = ValueError("boom")
    add_error_note(error, "fail", "my_event")
    add_error_note(error, "fail", "my_event")
    assert error.__notes__ == ["raised by fail while handling the event 'my_event'"]


def test_add_error_note_other_event_adds_note() -> None:
    error = ValueError("boom")
    add_error_note(error, "fail", "my_event")
    add_error_note(error, "fail", "my_other_event")
    assert error.__notes__ == [
        "raised by fail while handling the event 'my_event'",
        "raised by fail while handling the event 'my_other_event'",
    ]


def test_add_error_note_other_source_adds_note() -> None:
    error = ValueError("boom")
    add_error_note(error, "fail", "my_event")
    add_error_note(error, "hello_handler", "my_event")
    assert error.__notes__ == [
        "raised by fail while handling the event 'my_event'",
        "raised by hello_handler while handling the event 'my_event'",
    ]


def test_add_error_note_keeps_the_existing_notes() -> None:
    error = ValueError("boom")
    error.add_note("first")
    add_error_note(error, "fail", "my_event")
    assert error.__notes__ == ["first", "raised by fail while handling the event 'my_event'"]


def test_add_error_note_frozen_exception() -> None:
    error = FrozenError()
    add_error_note(error, "fail", "my_event")
    assert not hasattr(error, "__notes__")


@pytest.mark.parametrize("notes", [("first",), "first", 1])
def test_add_error_note_notes_not_a_list(notes: object) -> None:
    error: Any = ValueError("boom")
    error.__notes__ = notes
    add_error_note(error, "fail", "my_event")
    assert error.__notes__ == notes


class AddNoteRaisesError(Exception):
    r"""Implement an exception whose ``add_note`` raises."""

    def add_note(self, note: str) -> None:
        r"""Fail to add ``note``."""
        msg = f"cannot add {note}"
        raise RuntimeError(msg)


def test_add_error_note_add_note_raises() -> None:
    error = AddNoteRaisesError()
    add_error_note(error, "fail", "my_event")
    assert not hasattr(error, "__notes__")


def test_add_error_note_unprintable_event() -> None:
    class BadReprEvent(str):
        __slots__ = ()

        def __repr__(self) -> str:
            msg = "repr failed"
            raise RuntimeError(msg)

    error = ValueError("boom")
    add_error_note(error, "fail", BadReprEvent("my_event"))
    assert error.__notes__[0].startswith(
        "raised by fail while handling the event <BadReprEvent instance at "
    )


def test_add_error_note_long_event() -> None:
    error = ValueError("boom")
    add_error_note(error, "fail", "a" * 100 + "x" * 100_000 + "b" * 100)
    assert error.__notes__ == [
        (
            "raised by fail while handling the event "
            "'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            "aaaaaaaaaaaaaaaaaa...bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
            "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'"
        )
    ]
