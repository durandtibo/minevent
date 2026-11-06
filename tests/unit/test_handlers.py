from __future__ import annotations

import contextlib
import inspect
import logging
from collections.abc import Sequence
from types import MappingProxyType
from typing import Any
from unittest.mock import Mock

import pytest

from minevent import (
    AfterNCondition,
    BaseEventHandler,
    EventHandler,
    PeriodicCondition,
)
from minevent.handlers import _accepted_keywords
from tests.unit.utils import trace

logger = logging.getLogger(__name__)


@trace
def hello_handler() -> None:
    r"""Implements a simple handler that prints hello."""
    logger.info("Hello!")


@trace
def hello_name_handler(first_name: str, last_name: str) -> None:
    r"""Implements a simple handler that prints hello and the name of
    the person."""
    logger.info("Hello. I am %s %s", first_name, last_name)


def handle_n_times(event_handler: BaseEventHandler, n: int) -> None:
    r"""Call ``handle`` ``n`` times."""
    for _ in range(n):
        event_handler.handle()


def always_true() -> bool:
    return True


def always_false() -> bool:
    return False


##################################
#     Tests for EventHandler     #
##################################


def test_event_handler_str() -> None:
    assert str(EventHandler(hello_handler)).startswith("EventHandler(")


def test_event_handler__eq__same_instance() -> None:
    handler = EventHandler(hello_handler)
    assert handler == handler  # noqa: PLR0124


def test_event_handler__eq__compares_by_identity() -> None:
    assert EventHandler(hello_handler) != EventHandler(hello_handler)


def test_event_handler_hashable() -> None:
    handler = EventHandler(hello_handler)
    assert {handler: 1}[handler] == 1


def test_base_event_handler_hashable() -> None:
    class MyHandler(BaseEventHandler):
        def handle(self, /, **payload: Any) -> None:
            pass

    handler = MyHandler()
    assert {handler: 1}[handler] == 1


class AmbiguousSequence(Sequence):
    r"""Implements a sequence whose truth value is ambiguous, like an
    array."""

    def __init__(self, values: tuple[Any, ...]) -> None:
        self._values = values

    def __bool__(self) -> bool:
        msg = "The truth value is ambiguous"
        raise ValueError(msg)

    def __len__(self) -> int:
        return len(self._values)

    def __getitem__(self, index: int | slice) -> Any:
        return self._values[index]


class AmbiguousMapping(dict):
    r"""Implements a mapping whose truth value is ambiguous."""

    def __bool__(self) -> bool:
        msg = "The truth value is ambiguous"
        raise ValueError(msg)


def test_event_handler_handler_args_ambiguous_truth_value() -> None:
    event_handler = EventHandler(hello_name_handler, handler_args=AmbiguousSequence(("John",)))
    assert event_handler.handler_args == ("John",)


def test_event_handler_handler_args_empty_ambiguous_truth_value() -> None:
    assert EventHandler(hello_handler, handler_args=AmbiguousSequence(())).handler_args == ()


def test_event_handler_handler_kwargs_ambiguous_truth_value() -> None:
    event_handler = EventHandler(
        hello_name_handler, handler_kwargs=AmbiguousMapping(first_name="John")
    )
    assert event_handler.handler_kwargs == {"first_name": "John"}


def test_event_handler_handler_kwargs_empty_ambiguous_truth_value() -> None:
    assert EventHandler(hello_handler, handler_kwargs=AmbiguousMapping()).handler_kwargs == {}


def test_event_handler_without_args_and_kwargs() -> None:
    event_handler = EventHandler(hello_handler)
    assert (event_handler.handler, event_handler.handler_args, event_handler.handler_kwargs) == (
        hello_handler,
        (),
        {},
    )


def test_event_handler_with_only_args() -> None:
    event_handler = EventHandler(hello_name_handler, handler_args=("John", "Doe"))
    assert (event_handler.handler, event_handler.handler_args, event_handler.handler_kwargs) == (
        hello_name_handler,
        ("John", "Doe"),
        {},
    )


def test_event_handler_with_only_kwargs() -> None:
    event_handler = EventHandler(
        hello_name_handler, handler_kwargs={"first_name": "John", "last_name": "Doe"}
    )
    assert (event_handler.handler, event_handler.handler_args, event_handler.handler_kwargs) == (
        hello_name_handler,
        (),
        {"first_name": "John", "last_name": "Doe"},
    )


def test_event_handler_with_args_and_kwargs() -> None:
    event_handler = EventHandler(
        hello_handler, handler_args=("John",), handler_kwargs={"last_name": "Doe"}
    )
    assert (event_handler.handler, event_handler.handler_args, event_handler.handler_kwargs) == (
        hello_handler,
        ("John",),
        {"last_name": "Doe"},
    )


def test_event_handler_incorrect_handler() -> None:
    handler: Any = "abc"
    with pytest.raises(TypeError, match=r"handler is not callable:"):
        EventHandler(handler)


@pytest.mark.parametrize("handler_args", ["abc", b"abc"])
def test_event_handler_incorrect_handler_args(handler_args: str | bytes) -> None:
    with pytest.raises(TypeError, match=r"handler_args must be a sequence of arguments"):
        EventHandler(print, handler_args=handler_args)


def test_event_handler_handler_args_not_iterable() -> None:
    handler_args: Any = 5
    with pytest.raises(TypeError, match=r"handler_args must be a sequence of arguments, but got 5"):
        EventHandler(print, handler_args)


@pytest.mark.parametrize("handler_kwargs", [5, [1], "ab"])
def test_event_handler_incorrect_handler_kwargs(handler_kwargs: Any) -> None:
    with pytest.raises(TypeError, match=r"handler_kwargs must be a mapping, but got"):
        EventHandler(print, handler_kwargs=handler_kwargs)


def test_event_handler_handler_kwargs_message_names_value() -> None:
    handler_kwargs: Any = 5
    with pytest.raises(TypeError, match=r"handler_kwargs must be a mapping, but got 5"):
        EventHandler(print, handler_kwargs=handler_kwargs)


@pytest.mark.parametrize("handler_kwargs", [{1: 2}, {"a": 1, 2: 3}])
def test_event_handler_handler_kwargs_non_str_keys(handler_kwargs: dict[Any, Any]) -> None:
    with pytest.raises(TypeError, match=r"the keys of handler_kwargs must be str, but got"):
        EventHandler(print, handler_kwargs=handler_kwargs)


def test_event_handler_handler_kwargs_non_str_keys_message_lists_keys() -> None:
    handler_kwargs: Any = {"a": 1, 2: 3}
    with pytest.raises(TypeError, match=r"but got \['a', 2\]"):
        EventHandler(print, handler_kwargs=handler_kwargs)


def test_event_handler_handler_kwargs_empty() -> None:
    assert EventHandler(print, handler_kwargs={}).handler_kwargs == {}


def test_event_handler_handler_kwargs_mapping() -> None:
    assert EventHandler(print, handler_kwargs=MappingProxyType({"a": 1})).handler_kwargs == {"a": 1}


def test_event_handler_handle_without_args_and_kwargs() -> None:
    EventHandler(hello_handler).handle()
    assert hello_handler.call_count == 1
    assert hello_handler.args == ()
    assert hello_handler.kwargs == {}


def test_event_handler_handle_with_only_args() -> None:
    EventHandler(hello_name_handler, handler_args=("John", "Doe")).handle()
    assert hello_name_handler.call_count == 1
    assert hello_name_handler.args == ("John", "Doe")
    assert hello_name_handler.kwargs == {}


def test_event_handler_handle_with_only_kwargs() -> None:
    EventHandler(
        hello_name_handler, handler_kwargs={"first_name": "John", "last_name": "Doe"}
    ).handle()
    assert hello_name_handler.call_count == 1
    assert hello_name_handler.args == ()
    assert hello_name_handler.kwargs == {"first_name": "John", "last_name": "Doe"}


def test_event_handler_handle_with_args_and_kwargs() -> None:
    EventHandler(
        hello_name_handler, handler_args=("John",), handler_kwargs={"last_name": "Doe"}
    ).handle()
    assert hello_name_handler.call_count == 1
    assert hello_name_handler.args == ("John",)
    assert hello_name_handler.kwargs == {"last_name": "Doe"}


def test_event_handler_handle_called_2_times() -> None:
    event_handler = EventHandler(hello_handler)
    event_handler.handle()
    event_handler.handle()
    assert hello_handler.call_count == 2


############################################
#     Tests for EventHandler condition     #
############################################


def test_event_handler_condition_str() -> None:
    assert str(EventHandler(hello_handler, condition=PeriodicCondition(2))).startswith(
        "EventHandler("
    )


def test_event_handler_condition_property() -> None:
    condition = PeriodicCondition(3)
    assert EventHandler(hello_handler, condition=condition).condition is condition


def test_event_handler_condition_handle_1() -> None:
    EventHandler(hello_handler, condition=PeriodicCondition(3)).handle()
    assert hello_handler.call_count == 1
    assert hello_handler.args == ()
    assert hello_handler.kwargs == {}


def test_event_handler_condition_handle_10() -> None:
    handle_n_times(EventHandler(hello_handler, condition=PeriodicCondition(3)), 10)
    assert hello_handler.call_count == 4
    assert hello_handler.args == ()
    assert hello_handler.kwargs == {}


############################################
#     Tests for handler_kwargs copying     #
############################################


def test_event_handler_handler_kwargs_copied_on_construction() -> None:
    kwargs = {"first_name": "John", "last_name": "Doe"}
    event_handler = EventHandler(hello_name_handler, handler_kwargs=kwargs)
    kwargs["first_name"] = "Jane"
    assert event_handler.handler_kwargs == {"first_name": "John", "last_name": "Doe"}


def test_event_handler_handler_kwargs_property_returns_copy() -> None:
    event_handler = EventHandler(
        hello_name_handler, handler_kwargs={"first_name": "John", "last_name": "Doe"}
    )
    event_handler.handler_kwargs["first_name"] = "Jane"
    assert event_handler.handler_kwargs == {"first_name": "John", "last_name": "Doe"}


def test_event_handler_condition_handler_kwargs_copied_on_construction() -> None:
    kwargs = {"first_name": "John", "last_name": "Doe"}
    event_handler = EventHandler(
        hello_name_handler, condition=PeriodicCondition(1), handler_kwargs=kwargs
    )
    kwargs["first_name"] = "Jane"
    assert event_handler.handler_kwargs == {"first_name": "John", "last_name": "Doe"}


####################################
#     Tests for handle payload     #
####################################


def test_event_handler_handle_payload() -> None:
    EventHandler(hello_name_handler).handle(first_name="John", last_name="Doe")
    assert hello_name_handler.args == ()
    assert hello_name_handler.kwargs == {"first_name": "John", "last_name": "Doe"}


def test_event_handler_handle_payload_after_handler_args_and_kwargs() -> None:
    EventHandler(hello_name_handler, handler_args=("John",)).handle(last_name="Doe")
    assert hello_name_handler.args == ("John",)
    assert hello_name_handler.kwargs == {"last_name": "Doe"}


def test_event_handler_handle_payload_conflicts_with_handler_kwargs() -> None:
    event_handler = EventHandler(hello_name_handler, handler_kwargs={"first_name": "John"})
    with pytest.raises(TypeError, match=r"multiple values for keyword argument 'first_name'"):
        event_handler.handle(first_name="Jane", last_name="Doe")


@trace
def kwargs_handler(**kwargs: Any) -> None:
    r"""Implements a handler that accepts any keyword arguments."""
    logger.info("Kwargs: %s", kwargs)


def test_event_handler_handle_payload_with_self_key() -> None:
    EventHandler(kwargs_handler).handle(self=1)
    assert kwargs_handler.kwargs == {"self": 1}


async def test_event_handler_ahandle_payload_with_self_key() -> None:
    await EventHandler(kwargs_handler).ahandle(self=1)
    assert kwargs_handler.kwargs == {"self": 1}


async def test_base_event_handler_ahandle_payload_with_self_key() -> None:
    class MyHandler(BaseEventHandler):
        def handle(self, /, **payload: Any) -> None:
            kwargs_handler(**payload)

    await MyHandler().ahandle(self=1)
    assert kwargs_handler.kwargs == {"self": 1}


def test_event_handler_handle_payload_not_accepted_by_handler() -> None:
    with pytest.raises(TypeError, match=r"unexpected keyword argument 'epoch'"):
        EventHandler(hello_handler).handle(epoch=1)


def test_event_handler_condition_handle_payload_condition_true() -> None:
    EventHandler(hello_name_handler, condition=PeriodicCondition(2)).handle(
        first_name="John", last_name="Doe"
    )
    assert hello_name_handler.kwargs == {"first_name": "John", "last_name": "Doe"}


def test_event_handler_condition_handle_payload_condition_false() -> None:
    event_handler = EventHandler(hello_name_handler, condition=PeriodicCondition(2))
    event_handler.handle(first_name="John", last_name="Doe")
    event_handler.handle(first_name="Jane", last_name="Smith")
    assert hello_name_handler.kwargs == {"first_name": "John", "last_name": "Doe"}


def test_event_handler_condition_default() -> None:
    assert EventHandler(hello_handler).condition is None


def test_event_handler_repr_without_condition() -> None:
    assert repr(EventHandler(hello_handler, condition=None)).endswith(
        "condition=None, filter_payload=False)"
    )


def test_event_handler_repr_with_condition() -> None:
    assert "condition=PeriodicCondition(freq=2," in repr(
        EventHandler(hello_handler, condition=PeriodicCondition(2))
    )


##########################################################
#     Tests for EventHandler with callable condition     #
##########################################################


def test_event_handler_callable_condition_not_wrapped() -> None:
    assert EventHandler(hello_handler, condition=always_true).condition is always_true


def test_event_handler_callable_condition_true() -> None:
    EventHandler(hello_handler, condition=always_true).handle()
    assert hello_handler.call_count == 1


def test_event_handler_callable_condition_false() -> None:
    EventHandler(hello_handler, condition=always_false).handle()
    assert hello_handler.call_count == 0


def test_event_handler_condition_incorrect_type() -> None:
    bad: Any = "meow"
    with pytest.raises(TypeError, match=r"condition is not callable: meow"):
        EventHandler(hello_handler, condition=bad)


def test_event_handler_condition_combinator_short_circuit() -> None:
    after_one = AfterNCondition(1)
    periodic = PeriodicCondition(2)
    handle_n_times(
        EventHandler(hello_handler, condition=lambda: after_one() and periodic()),
        5,
    )
    assert hello_handler.call_count == 2


def test_event_handler_condition_combinator_short_circuit_skips_second_condition() -> None:
    periodic = PeriodicCondition(2)
    first = Mock(return_value=False)
    handle_n_times(EventHandler(hello_handler, condition=lambda: first() and periodic()), 3)
    assert periodic._step == 0


def test_event_handler_condition_combinator_evaluates_all() -> None:
    periodic = PeriodicCondition(2)
    handle_n_times(EventHandler(hello_handler, condition=lambda: all([False, periodic()])), 3)
    assert periodic._step == 3


########################################
#     Tests for equality semantics     #
########################################


#############################
#     Tests for ahandle     #
#############################


@trace
async def async_hello_handler() -> None:
    r"""Implements a simple coroutine handler."""
    logger.info("Hello async!")


@trace
async def async_name_handler(first_name: str, last_name: str) -> None:
    r"""Implements a coroutine handler with arguments."""
    logger.info("Hello async. I am %s %s", first_name, last_name)


def test_event_handler_handle_coroutine_raises() -> None:
    with pytest.raises(TypeError, match=r"returned an awaitable; use ahandle or atrigger_event"):
        EventHandler(async_hello_handler).handle()


def test_event_handler_handle_coroutine_is_closed() -> None:
    coroutines = []

    def make_coroutine() -> object:
        coroutine = async_hello_handler()
        coroutines.append(coroutine)
        return coroutine

    with contextlib.suppress(TypeError):
        EventHandler(make_coroutine).handle()
    assert inspect.getcoroutinestate(coroutines[0]) == inspect.CORO_CLOSED


def test_event_handler_handle_awaitable_raises() -> None:
    class Awaitable:
        def __await__(self) -> Any:
            yield

    with pytest.raises(TypeError, match=r"returned an awaitable"):
        EventHandler(Awaitable).handle()


def test_event_handler_handle_coroutine_condition_false_does_not_call() -> None:
    EventHandler(async_hello_handler, condition=lambda: False).handle()
    assert async_hello_handler.call_count == 0


async def test_event_handler_ahandle_coroutine_awaited() -> None:
    awaited = []

    async def handler() -> None:
        awaited.append(1)

    await EventHandler(handler).ahandle()
    assert awaited == [1]


async def test_event_handler_ahandle_awaits_object_with_await() -> None:
    awaited = []

    class Awaitable:
        def __await__(self) -> Any:
            awaited.append(1)
            yield

    await EventHandler(Awaitable).ahandle()
    assert awaited == [1]


async def test_event_handler_ahandle_sync_handler() -> None:
    await EventHandler(hello_handler).ahandle()
    assert hello_handler.call_count == 1


async def test_event_handler_ahandle_payload_and_arguments() -> None:
    await EventHandler(async_name_handler, handler_args=("John",)).ahandle(last_name="Doe")
    assert async_name_handler.kwargs == {"last_name": "Doe"}


async def test_event_handler_ahandle_condition_false() -> None:
    await EventHandler(hello_handler, condition=always_false).ahandle()
    assert hello_handler.call_count == 0


async def test_event_handler_ahandle_condition_true() -> None:
    await EventHandler(hello_handler, condition=always_true).ahandle()
    assert hello_handler.call_count == 1


async def test_event_handler_ahandle_coroutine_error_propagates() -> None:
    async def handler() -> None:
        msg = "async failed"
        raise RuntimeError(msg)

    with pytest.raises(RuntimeError, match=r"async failed"):
        await EventHandler(handler).ahandle()


async def test_base_event_handler_ahandle_calls_handle() -> None:
    class MyHandler(BaseEventHandler):
        def handle(self, /, **payload: Any) -> None:
            hello_handler(**payload)

    await MyHandler().ahandle()
    assert hello_handler.call_count == 1


####################################
#     Tests for filter_payload     #
####################################


@trace
def epoch_handler(epoch: int) -> None:
    logger.info("epoch %s", epoch)


@trace
def keyword_only_handler(*, loss: float) -> None:
    logger.info("loss %s", loss)


class UninspectableCallable:
    r"""Implements a callable whose signature cannot be inspected."""

    __signature__ = 1

    def __call__(self, **kwargs: Any) -> None:
        logger.info("Kwargs: %s", kwargs)


def positional_only_handler(epoch: int, /) -> None:
    logger.info("epoch %s", epoch)


def test_event_handler_filter_payload_default() -> None:
    assert not EventHandler(hello_handler).filter_payload


def test_event_handler_filter_payload_true() -> None:
    assert EventHandler(hello_handler, filter_payload=True).filter_payload


def test_event_handler_filter_payload_keeps_accepted_keys() -> None:
    handler = EventHandler(epoch_handler, filter_payload=True)
    handler.handle(epoch=3, loss=0.5)
    assert epoch_handler.kwargs == {"epoch": 3}


def test_event_handler_filter_payload_false_raises_for_unknown_key() -> None:
    with pytest.raises(TypeError, match=r"unexpected keyword argument 'loss'"):
        EventHandler(epoch_handler).handle(epoch=3, loss=0.5)


def test_event_handler_filter_payload_no_parameter() -> None:
    EventHandler(hello_handler, filter_payload=True).handle(epoch=3)
    assert hello_handler.call_count == 1


def test_event_handler_filter_payload_keyword_only_parameter() -> None:
    EventHandler(keyword_only_handler, filter_payload=True).handle(epoch=3, loss=0.5)
    assert keyword_only_handler.kwargs == {"loss": 0.5}


def test_event_handler_filter_payload_var_keyword_receives_everything() -> None:
    EventHandler(kwargs_handler, filter_payload=True).handle(epoch=3, loss=0.5)
    assert kwargs_handler.kwargs == {"epoch": 3, "loss": 0.5}


def test_event_handler_filter_payload_missing_key_still_raises() -> None:
    with pytest.raises(TypeError, match=r"missing 1 required positional argument: 'epoch'"):
        EventHandler(epoch_handler, filter_payload=True).handle(loss=0.5)


def test_event_handler_filter_payload_positional_only_not_passed() -> None:
    with pytest.raises(TypeError, match=r"missing 1 required positional argument"):
        EventHandler(positional_only_handler, filter_payload=True).handle(epoch=3)


def test_event_handler_filter_payload_handler_kwargs_not_filtered() -> None:
    handler = EventHandler(epoch_handler, handler_kwargs={"epoch": 1}, filter_payload=True)
    handler.handle(loss=0.5)
    assert epoch_handler.kwargs == {"epoch": 1}


async def test_event_handler_filter_payload_ahandle() -> None:
    await EventHandler(epoch_handler, filter_payload=True).ahandle(epoch=3, loss=1)
    assert epoch_handler.kwargs == {"epoch": 3}


async def test_event_handler_filter_payload_ahandle_coroutine() -> None:
    await EventHandler(async_name_handler, filter_payload=True).ahandle(
        first_name="A", last_name="B", x=1
    )
    assert async_name_handler.kwargs == {"first_name": "A", "last_name": "B"}


def test_event_handler_filter_payload_uninspectable_receives_everything() -> None:
    EventHandler(UninspectableCallable(), filter_payload=True).handle(epoch=3)


def test_accepted_keywords_uninspectable() -> None:
    assert _accepted_keywords(UninspectableCallable()) is None


def test_event_handler_repr_filter_payload_true() -> None:
    assert repr(EventHandler(hello_handler, filter_payload=True)).endswith("filter_payload=True)")


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
    assert _accepted_keywords(hello_name_handler) == frozenset({"first_name", "last_name"})


#############################
#     Tests for _call     #
#############################


def test_event_handler_call_returns_handler_result() -> None:
    assert EventHandler(lambda: 42)._call({}) == 42


def test_event_handler_call_passes_args_kwargs_and_payload() -> None:
    handler = EventHandler(
        lambda *args, **kwargs: (args, kwargs), handler_args=(1,), handler_kwargs={"a": 2}
    )
    assert handler._call({"b": 3}) == ((1,), {"a": 2, "b": 3})


def test_event_handler_call_condition_false_returns_none_without_calling() -> None:
    handler = EventHandler(hello_handler, condition=always_false)
    handler._call({})
    assert hello_handler.call_count == 0


def test_event_handler_call_condition_false_returns_none() -> None:
    assert EventHandler(lambda: 42, condition=always_false)._call({}) is None


def test_event_handler_call_condition_true_returns_handler_result() -> None:
    assert EventHandler(lambda: 42, condition=always_true)._call({}) == 42


def test_event_handler_call_filters_payload() -> None:
    handler = EventHandler(lambda epoch: epoch, filter_payload=True)
    assert handler._call({"epoch": 3, "loss": 0.5}) == 3


def test_event_handler_repr_full() -> None:
    assert repr(EventHandler(print, handler_args=("hello",), handler_kwargs={"end": ""})) == (
        "EventHandler(handler=<built-in function print>, handler_args=('hello',), "
        "handler_kwargs={'end': ''}, condition=None, filter_payload=False)"
    )
