from __future__ import annotations

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

from coola import EqualityTester, objects_are_equal
from pytest import LogCaptureFixture, fixture, raises

from minevent import (
    BaseEventHandler,
    ConditionalEventHandler,
    EventHandler,
    PeriodicCondition,
)
from minevent.comparators import EventHandlerEqualityOperator

logger = logging.getLogger(__name__)


def trace(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        wrapper.called = True
        wrapper.call_count += 1
        wrapper.args = args
        wrapper.kwargs = kwargs
        return func(*args, **kwargs)

    wrapper.called = False
    wrapper.call_count = 0
    wrapper.args = ()
    wrapper.kwargs = {}
    return wrapper


@trace
def hello_handler() -> None:
    r"""Implements a simple handler that prints hello."""
    print("Hello!")


@trace
def hello_name_handler(first_name: str, last_name: str) -> None:
    r"""Implements a simple handler that prints hello and the name of
    the person."""
    logger.info(f"Hello. I am {first_name} {last_name}")


@fixture(scope="function", autouse=True)
def reset_tracer() -> None:
    def reset_func(func: Callable) -> None:
        func.called = False
        func.call_count = 0
        func.args = ()
        func.kwargs = {}

    reset_func(hello_handler)
    reset_func(hello_name_handler)


def test_registered_event_handler_comparators() -> None:
    assert isinstance(EqualityTester.registry[BaseEventHandler], EventHandlerEqualityOperator)


##################################
#     Tests for EventHandler     #
##################################


def test_event_handler_str() -> None:
    assert str(EventHandler(hello_handler)).startswith("EventHandler(")


def test_event_handler_equal_true() -> None:
    assert EventHandler(hello_handler).equal(EventHandler(hello_handler))


def test_event_handler_equal_false_same_class_different_handler_args() -> None:
    assert not EventHandler(hello_handler).equal(
        EventHandler(hello_handler, handler_args=("something",))
    )


def test_event_handler_equal_false_same_class_different_handler_kwargs() -> None:
    assert not EventHandler(hello_handler).equal(
        EventHandler(hello_handler, handler_kwargs={"something": "abc"})
    )


def test_event_handler_equal_false_different_classes() -> None:
    assert not EventHandler(hello_handler).equal(
        ConditionalEventHandler(hello_name_handler, PeriodicCondition(3))
    )


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
    with raises(TypeError, match="handler is not callable:"):
        EventHandler("abc")


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


#############################################
#     Tests for ConditionalEventHandler     #
#############################################


def test_conditional_event_handler_str() -> None:
    assert str(ConditionalEventHandler(hello_handler, PeriodicCondition(2))).startswith(
        "ConditionalEventHandler("
    )


def test_conditional_event_handler_equal_true() -> None:
    h1 = ConditionalEventHandler(hello_handler, PeriodicCondition(3))
    h2 = ConditionalEventHandler(hello_handler, PeriodicCondition(3))
    print(h1)
    print(h2)
    print(h1.handler == h2.handler, objects_are_equal(h1.handler, h2.handler))
    print(h1.handler_args == h2.handler_args, objects_are_equal(h1.handler_args, h2.handler_args))
    print(
        h1.handler_kwargs == h2.handler_kwargs,
        objects_are_equal(h1.handler_kwargs, h2.handler_kwargs),
    )
    print(h1.condition == h2.condition, objects_are_equal(h1.condition, h2.condition))
    assert ConditionalEventHandler(hello_handler, PeriodicCondition(3)).equal(
        ConditionalEventHandler(hello_handler, PeriodicCondition(3))
    )


def test_conditional_event_handler_equal_false_same_class_different_handler_args() -> None:
    assert not ConditionalEventHandler(hello_handler, condition=PeriodicCondition(2)).equal(
        ConditionalEventHandler(
            hello_handler, handler_args=("meow",), condition=PeriodicCondition(2)
        )
    )


def test_conditional_event_handler_equal_false_same_class_different_handler_kwargs() -> None:
    assert not ConditionalEventHandler(hello_handler, condition=PeriodicCondition(2)).equal(
        ConditionalEventHandler(
            hello_handler, handler_kwargs={"key": "meow"}, condition=PeriodicCondition(2)
        )
    )


def test_conditional_event_handler_equal_false_same_class_different_conditions() -> None:
    assert not ConditionalEventHandler(hello_handler, PeriodicCondition(3)).equal(
        ConditionalEventHandler(hello_handler, PeriodicCondition(2))
    )


def test_conditional_event_handler_equal_false_different_classes() -> None:
    assert not ConditionalEventHandler(hello_handler, PeriodicCondition(3)).equal(
        EventHandler(hello_name_handler)
    )


def test_conditional_event_handler_callable_condition() -> None:
    event_handler = ConditionalEventHandler(hello_handler, PeriodicCondition(3))
    assert event_handler.handler == hello_handler
    assert event_handler.handler_args == ()
    assert event_handler.handler_kwargs == {}
    assert event_handler.condition == PeriodicCondition(3)


def test_conditional_event_handler_non_callable_condition() -> None:
    with raises(TypeError, match="The condition is not callable"):
        ConditionalEventHandler(hello_handler, 123)


def test_event_handler_handle_1() -> None:
    ConditionalEventHandler(hello_handler, PeriodicCondition(3)).handle()
    assert hello_handler.called
    assert hello_handler.call_count == 1
    assert hello_handler.args == ()
    assert hello_handler.kwargs == {}


def test_event_handler_handle_10() -> None:
    event_handler = ConditionalEventHandler(hello_handler, PeriodicCondition(3))
    for _ in range(10):
        event_handler.handle()
    assert hello_handler.called
    assert hello_handler.call_count == 4
    assert hello_handler.args == ()
    assert hello_handler.kwargs == {}


##################################################
#     Tests for EventHandlerEqualityOperator     #
##################################################


def test_event_handler_equality_operator_str() -> None:
    assert str(EventHandlerEqualityOperator()) == "EventHandlerEqualityOperator()"


def test_event_handler_equality_operator__eq__true() -> None:
    assert EventHandlerEqualityOperator() == EventHandlerEqualityOperator()


def test_event_handler_equality_operator__eq__false() -> None:
    assert EventHandlerEqualityOperator() != 123


def test_event_handler_equality_operator_clone() -> None:
    op = EventHandlerEqualityOperator()
    op_cloned = op.clone()
    assert op is not op_cloned
    assert op == op_cloned


def test_event_handler_equality_operator_equal_true() -> None:
    assert EventHandlerEqualityOperator().equal(
        EqualityTester(), EventHandler(hello_handler), EventHandler(hello_handler)
    )


def test_event_handler_equality_operator_equal_true_same_object() -> None:
    handler = EventHandler(hello_handler)
    assert EventHandlerEqualityOperator().equal(EqualityTester(), handler, handler)


def test_event_handler_equality_operator_equal_true_show_difference(
    caplog: LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO):
        assert EventHandlerEqualityOperator().equal(
            tester=EqualityTester(),
            object1=EventHandler(hello_handler),
            object2=EventHandler(hello_handler),
            show_difference=True,
        )
        assert not caplog.messages


def test_event_handler_equality_operator_equal_false_different_value() -> None:
    assert not EventHandlerEqualityOperator().equal(
        EqualityTester(), EventHandler(hello_handler), EventHandler(hello_name_handler)
    )


def test_event_handler_equality_operator_equal_false_different_value_show_difference(
    caplog: LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO):
        assert not EventHandlerEqualityOperator().equal(
            tester=EqualityTester(),
            object1=EventHandler(hello_handler),
            object2=EventHandler(hello_name_handler),
            show_difference=True,
        )
        assert caplog.messages[0].startswith("`BaseEventHandler` objects are different")


def test_event_handler_equality_operator_equal_false_different_type() -> None:
    assert not EventHandlerEqualityOperator().equal(
        EqualityTester(), EventHandler(hello_handler), 42
    )


def test_event_handler_equality_operator_equal_false_different_type_show_difference(
    caplog: LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO):
        assert not EventHandlerEqualityOperator().equal(
            tester=EqualityTester(),
            object1=EventHandler(hello_handler),
            object2=42,
            show_difference=True,
        )
        assert caplog.messages[0].startswith("object2 is not a `BaseEventHandler` object")
