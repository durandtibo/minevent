from __future__ import annotations

import logging

from coola import EqualityTester
from pytest import LogCaptureFixture

from minevent import BaseEventHandler, EventHandler
from minevent.comparators import EventHandlerEqualityOperator
from tests.unit.test_handlers import hello_handler, hello_name_handler

logger = logging.getLogger(__name__)


def test_registered_event_handler_comparators() -> None:
    assert isinstance(EqualityTester.registry[BaseEventHandler], EventHandlerEqualityOperator)


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