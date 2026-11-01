from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from minevent import ConditionalEventHandler, EventHandler, PeriodicCondition
from tests.unit.utils import trace

if TYPE_CHECKING:
    from collections.abc import Callable

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


@pytest.fixture(autouse=True)
def _reset_tracer() -> None:
    def reset_func(func: Callable) -> None:
        func.called = False
        func.call_count = 0
        func.args = ()
        func.kwargs = {}

    reset_func(hello_handler)
    reset_func(hello_name_handler)


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
    with pytest.raises(TypeError, match=r"handler is not callable:"):
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


def test_conditional_event_handler_handler_kwargs_copied_on_construction() -> None:
    kwargs = {"first_name": "John", "last_name": "Doe"}
    event_handler = ConditionalEventHandler(
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


def test_event_handler_handle_payload_not_accepted_by_handler() -> None:
    with pytest.raises(TypeError, match=r"unexpected keyword argument 'epoch'"):
        EventHandler(hello_handler).handle(epoch=1)


def test_conditional_event_handler_handle_payload_condition_true() -> None:
    ConditionalEventHandler(hello_name_handler, PeriodicCondition(2)).handle(
        first_name="John", last_name="Doe"
    )
    assert hello_name_handler.kwargs == {"first_name": "John", "last_name": "Doe"}


def test_conditional_event_handler_handle_payload_condition_false() -> None:
    event_handler = ConditionalEventHandler(hello_name_handler, PeriodicCondition(2))
    event_handler.handle(first_name="John", last_name="Doe")
    event_handler.handle(first_name="Jane", last_name="Smith")
    assert hello_name_handler.kwargs == {"first_name": "John", "last_name": "Doe"}
