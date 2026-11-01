from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Sequence
from types import MappingProxyType
from typing import Any

import pytest

from minevent import (
    AfterNCondition,
    AndCondition,
    BaseEventHandler,
    CallableCondition,
    ConditionalEventHandler,
    EventHandler,
    PeriodicCondition,
)
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


def always_true() -> bool:
    return True


def always_false() -> bool:
    return False


@pytest.fixture(autouse=True)
def _reset_tracer() -> None:
    hello_handler.reset()
    hello_name_handler.reset()
    async_hello_handler.reset()
    async_name_handler.reset()
    kwargs_handler.reset()


##################################
#     Tests for EventHandler     #
##################################


def test_event_handler_str() -> None:
    assert str(EventHandler(hello_handler)).startswith("EventHandler(")


def test_event_handler__eq__true() -> None:
    assert EventHandler(hello_handler) == EventHandler(hello_handler)


def test_event_handler__eq__false() -> None:
    assert EventHandler(hello_handler) != EventHandler(hello_name_handler)


def test_event_handler_equal_true() -> None:
    assert EventHandler(hello_handler).equal(EventHandler(hello_handler))


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


def test_event_handler_equal_false_same_class_different_handler_args() -> None:
    assert not EventHandler(hello_handler).equal(
        EventHandler(hello_handler, handler_args=("something",))
    )


def test_event_handler_equal_false_same_class_different_handler_kwargs() -> None:
    assert not EventHandler(hello_handler).equal(
        EventHandler(hello_handler, handler_kwargs={"something": "abc"})
    )


def test_event_handler_equal_false_different_classes() -> None:
    assert not EventHandler(hello_handler).equal("meow")


def test_event_handler_without_args_and_kwargs() -> None:
    event_handler = EventHandler(hello_handler)
    assert event_handler.handler == hello_handler
    assert event_handler.handler_args == ()
    assert event_handler.handler_kwargs == {}


def test_event_handler_with_only_args() -> None:
    event_handler = EventHandler(hello_name_handler, handler_args=("John", "Doe"))
    assert event_handler.handler == hello_name_handler
    assert event_handler.handler_args == ("John", "Doe")
    assert event_handler.handler_kwargs == {}


def test_event_handler_with_only_kwargs() -> None:
    event_handler = EventHandler(
        hello_name_handler, handler_kwargs={"first_name": "John", "last_name": "Doe"}
    )
    assert event_handler.handler == hello_name_handler
    assert event_handler.handler_args == ()
    assert event_handler.handler_kwargs == {"first_name": "John", "last_name": "Doe"}


def test_event_handler_with_args_and_kwargs() -> None:
    event_handler = EventHandler(
        hello_handler, handler_args=("John",), handler_kwargs={"last_name": "Doe"}
    )
    assert event_handler.handler == hello_handler
    assert event_handler.handler_args == ("John",)
    assert event_handler.handler_kwargs == {"last_name": "Doe"}


def test_event_handler_incorrect_handler() -> None:
    handler: Any = "abc"
    with pytest.raises(TypeError, match=r"handler is not callable:"):
        EventHandler(handler)


@pytest.mark.parametrize("handler_args", ["abc", b"abc"])
def test_event_handler_incorrect_handler_args(handler_args: str | bytes) -> None:
    with pytest.raises(TypeError, match=r"handler_args must be a sequence of arguments"):
        EventHandler(print, handler_args=handler_args)


def test_event_handler_handler_kwargs_mapping() -> None:
    assert EventHandler(print, handler_kwargs=MappingProxyType({"a": 1})).handler_kwargs == {"a": 1}


def test_event_handler_handle_without_args_and_kwargs() -> None:
    EventHandler(hello_handler).handle()
    assert hello_handler.called
    assert hello_handler.call_count == 1
    assert hello_handler.args == ()
    assert hello_handler.kwargs == {}


def test_event_handler_handle_with_only_args() -> None:
    EventHandler(hello_name_handler, handler_args=("John", "Doe")).handle()
    assert hello_name_handler.called
    assert hello_name_handler.call_count == 1
    assert hello_name_handler.args == ("John", "Doe")
    assert hello_name_handler.kwargs == {}


def test_event_handler_handle_with_only_kwargs() -> None:
    EventHandler(
        hello_name_handler, handler_kwargs={"first_name": "John", "last_name": "Doe"}
    ).handle()
    assert hello_name_handler.called
    assert hello_name_handler.call_count == 1
    assert hello_name_handler.args == ()
    assert hello_name_handler.kwargs == {"first_name": "John", "last_name": "Doe"}


def test_event_handler_handle_with_args_and_kwargs() -> None:
    EventHandler(
        hello_name_handler, handler_args=("John",), handler_kwargs={"last_name": "Doe"}
    ).handle()
    assert hello_name_handler.called
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


def test_event_handler_condition_equal_true() -> None:
    assert EventHandler(hello_handler, condition=PeriodicCondition(3)).equal(
        EventHandler(hello_handler, condition=PeriodicCondition(3))
    )


def test_event_handler_condition_equal_false_same_class_different_handler_args() -> None:
    assert not EventHandler(hello_handler, condition=PeriodicCondition(2)).equal(
        EventHandler(hello_handler, handler_args=("meow",), condition=PeriodicCondition(2))
    )


def test_event_handler_condition_equal_false_same_class_different_handler_kwargs() -> None:
    assert not EventHandler(hello_handler, condition=PeriodicCondition(2)).equal(
        EventHandler(hello_handler, handler_kwargs={"key": "meow"}, condition=PeriodicCondition(2))
    )


def test_event_handler_condition_equal_false_same_class_different_conditions() -> None:
    assert not EventHandler(hello_handler, condition=PeriodicCondition(3)).equal(
        EventHandler(hello_handler, condition=PeriodicCondition(2))
    )


def test_event_handler_condition_equal_false_different_classes() -> None:
    assert not EventHandler(hello_handler, condition=PeriodicCondition(3)).equal(
        EventHandler(hello_name_handler)
    )


def test_event_handler_condition_callable_condition() -> None:
    event_handler = EventHandler(hello_handler, condition=PeriodicCondition(3))
    assert event_handler.handler == hello_handler
    assert event_handler.handler_args == ()
    assert event_handler.handler_kwargs == {}
    assert event_handler.condition == PeriodicCondition(3)


def test_event_handler_condition_handle_1() -> None:
    EventHandler(hello_handler, condition=PeriodicCondition(3)).handle()
    assert hello_handler.called
    assert hello_handler.call_count == 1
    assert hello_handler.args == ()
    assert hello_handler.kwargs == {}


def test_event_handler_condition_handle_10() -> None:
    event_handler = EventHandler(hello_handler, condition=PeriodicCondition(3))
    for _ in range(10):
        event_handler.handle()
    assert hello_handler.called
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


def test_event_handler_equal_unchanged_after_mutating_caller_kwargs() -> None:
    kwargs = {"first_name": "John", "last_name": "Doe"}
    event_handler = EventHandler(hello_name_handler, handler_kwargs=kwargs)
    kwargs["first_name"] = "Jane"
    assert event_handler.equal(
        EventHandler(hello_name_handler, handler_kwargs={"first_name": "John", "last_name": "Doe"})
    )


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


def test_event_handler_ahandle_payload_with_self_key() -> None:
    asyncio.run(EventHandler(kwargs_handler).ahandle(self=1))
    assert kwargs_handler.kwargs == {"self": 1}


def test_base_event_handler_ahandle_payload_with_self_key() -> None:
    class MyHandler(BaseEventHandler):
        def equal(self, other: Any) -> bool:
            return self is other

        def handle(self, /, **payload: Any) -> None:
            kwargs_handler(**payload)

    asyncio.run(MyHandler().ahandle(self=1))
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


def test_event_handler_condition_repr_without_condition() -> None:
    assert "condition" not in repr(EventHandler(hello_handler))


def test_event_handler_condition_repr_with_condition() -> None:
    assert "(condition): PeriodicCondition(freq=2," in repr(
        EventHandler(hello_handler, condition=PeriodicCondition(2))
    )


def test_event_handler_condition_equal_false_with_and_without_condition() -> None:
    assert not EventHandler(hello_handler).equal(
        EventHandler(hello_handler, condition=PeriodicCondition(2))
    )


def test_event_handler_equal_false_subclass() -> None:
    class MyEventHandler(EventHandler):
        pass

    assert not EventHandler(hello_handler).equal(MyEventHandler(hello_handler))


def test_event_handler_equal_true_same_subclass() -> None:
    class MyEventHandler(EventHandler):
        pass

    assert MyEventHandler(hello_handler).equal(MyEventHandler(hello_handler))


#############################################
#     Tests for ConditionalEventHandler     #
#############################################


def test_conditional_event_handler_warns() -> None:
    with pytest.warns(DeprecationWarning, match=r"ConditionalEventHandler is deprecated"):
        ConditionalEventHandler(hello_handler, PeriodicCondition(2))


def test_conditional_event_handler_returns_event_handler() -> None:
    with pytest.warns(DeprecationWarning, match=r"ConditionalEventHandler is deprecated"):
        event_handler = ConditionalEventHandler(hello_handler, PeriodicCondition(2))
    assert type(event_handler) is EventHandler


def test_conditional_event_handler_equal_event_handler_with_condition() -> None:
    with pytest.warns(DeprecationWarning, match=r"ConditionalEventHandler is deprecated"):
        event_handler = ConditionalEventHandler(hello_handler, PeriodicCondition(2))
    assert event_handler.equal(EventHandler(hello_handler, condition=PeriodicCondition(2)))


def test_conditional_event_handler_arguments() -> None:
    with pytest.warns(DeprecationWarning, match=r"ConditionalEventHandler is deprecated"):
        event_handler = ConditionalEventHandler(
            hello_name_handler,
            PeriodicCondition(2),
            handler_args=("John",),
            handler_kwargs={"last_name": "Doe"},
        )
    event_handler.handle()
    assert hello_name_handler.kwargs == {"last_name": "Doe"}


def test_event_handler_key() -> None:
    condition = PeriodicCondition(2)
    event_handler = EventHandler(
        hello_name_handler,
        handler_args=("John",),
        handler_kwargs={"last_name": "Doe"},
        condition=condition,
    )
    assert event_handler._key() == (hello_name_handler, ("John",), {"last_name": "Doe"}, condition)


def test_event_handler_key_without_condition() -> None:
    assert EventHandler(hello_handler)._key() == (hello_handler, (), {}, None)


##########################################################
#     Tests for EventHandler with callable condition     #
##########################################################


def test_event_handler_callable_condition_wrapped() -> None:
    assert EventHandler(hello_handler, condition=always_true).condition == CallableCondition(
        always_true
    )


def test_event_handler_callable_condition_true() -> None:
    EventHandler(hello_handler, condition=always_true).handle()
    assert hello_handler.call_count == 1


def test_event_handler_callable_condition_false() -> None:
    EventHandler(hello_handler, condition=always_false).handle()
    assert hello_handler.call_count == 0


def test_event_handler_callable_condition_equal_true() -> None:
    assert EventHandler(hello_handler, condition=always_true).equal(
        EventHandler(hello_handler, condition=always_true)
    )


def test_event_handler_callable_condition_equal_false() -> None:
    assert not EventHandler(hello_handler, condition=always_true).equal(
        EventHandler(hello_handler, condition=always_false)
    )


def test_event_handler_condition_incorrect_type() -> None:
    bad: Any = "meow"
    with pytest.raises(TypeError, match=r"condition must be a BaseCondition or a callable"):
        EventHandler(hello_handler, condition=bad)


def test_event_handler_condition_combinator() -> None:
    event_handler = EventHandler(
        hello_handler, condition=AndCondition(AfterNCondition(1), PeriodicCondition(2))
    )
    for _ in range(5):
        event_handler.handle()
    assert hello_handler.call_count == 2


########################################
#     Tests for equality semantics     #
########################################


def test_event_handler_unhashable() -> None:
    with pytest.raises(TypeError, match=r"unhashable type: 'EventHandler'"):
        hash(EventHandler(hello_handler))


def test_event_handler_equal_false_different_lambdas() -> None:
    assert not EventHandler(lambda: None).equal(EventHandler(lambda: None))


def test_event_handler_equal_true_same_lambda() -> None:
    func = lambda: None  # noqa: E731
    assert EventHandler(func).equal(EventHandler(func))


def test_event_handler_equal_true_same_bound_method() -> None:
    obj = EventHandler(hello_handler)
    assert EventHandler(obj.handle).equal(EventHandler(obj.handle))


def test_event_handler_equal_false_bound_methods_of_different_instances() -> None:
    assert not EventHandler(EventHandler(hello_handler).handle).equal(
        EventHandler(EventHandler(hello_handler).handle)
    )


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

    with pytest.raises(TypeError, match=r"returned an awaitable"):
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


def test_event_handler_ahandle_coroutine_awaited() -> None:
    awaited = []

    async def handler() -> None:
        awaited.append(1)

    asyncio.run(EventHandler(handler).ahandle())
    assert awaited == [1]


def test_event_handler_ahandle_sync_handler() -> None:
    asyncio.run(EventHandler(hello_handler).ahandle())
    assert hello_handler.call_count == 1


def test_event_handler_ahandle_payload_and_arguments() -> None:
    asyncio.run(EventHandler(async_name_handler, handler_args=("John",)).ahandle(last_name="Doe"))
    assert async_name_handler.kwargs == {"last_name": "Doe"}


def test_event_handler_ahandle_condition_false() -> None:
    asyncio.run(EventHandler(hello_handler, condition=always_false).ahandle())
    assert hello_handler.call_count == 0


def test_event_handler_ahandle_condition_true() -> None:
    asyncio.run(EventHandler(hello_handler, condition=always_true).ahandle())
    assert hello_handler.call_count == 1


def test_event_handler_ahandle_coroutine_error_propagates() -> None:
    async def handler() -> None:
        msg = "async failed"
        raise RuntimeError(msg)

    with pytest.raises(RuntimeError, match=r"async failed"):
        asyncio.run(EventHandler(handler).ahandle())


def test_base_event_handler_ahandle_calls_handle() -> None:
    class MyHandler(BaseEventHandler):
        def equal(self, other: Any) -> bool:
            return self is other

        def handle(self, /, **payload: Any) -> None:
            hello_handler(**payload)

    asyncio.run(MyHandler().ahandle())
    assert hello_handler.call_count == 1
