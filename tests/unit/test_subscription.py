from __future__ import annotations

from unittest.mock import Mock

import pytest

from minevent import EventHandler, Subscription


def failing_handler() -> None:
    msg = "handler failed"
    raise RuntimeError(msg)


##################################
#     Tests for Subscription     #
##################################


def test_subscription_repr() -> None:
    assert repr(Subscription("my_event", EventHandler(print), Mock())) == (
        "Subscription(event='my_event')"
    )


def test_subscription_event() -> None:
    assert Subscription("my_event", EventHandler(print), Mock()).event == "my_event"


def test_subscription_event_handler() -> None:
    handler = EventHandler(print)
    assert Subscription("my_event", handler, Mock()).event_handler is handler


def test_subscription_remove_calls_remove_func() -> None:
    handler = EventHandler(print)
    remove_func = Mock(return_value=True)
    Subscription("my_event", handler, remove_func).remove()
    remove_func.assert_called_once_with("my_event", handler)


def test_subscription_remove_returns_true() -> None:
    assert Subscription("my_event", EventHandler(print), Mock(return_value=True)).remove()


def test_subscription_remove_returns_false() -> None:
    assert not Subscription("my_event", EventHandler(print), Mock(return_value=False)).remove()


def test_subscription_active_without_func_before_remove() -> None:
    assert Subscription("my_event", EventHandler(print), Mock()).active


def test_subscription_active_without_func_after_remove() -> None:
    subscription = Subscription("my_event", EventHandler(print), Mock())
    subscription.remove()
    assert not subscription.active


def test_subscription_active_calls_is_active_func() -> None:
    handler = EventHandler(print)
    is_active_func = Mock(return_value=False)
    assert not Subscription("my_event", handler, Mock(), is_active_func=is_active_func).active
    is_active_func.assert_called_once_with("my_event", handler)


def test_subscription_enter_returns_subscription() -> None:
    subscription = Subscription("my_event", EventHandler(print), Mock())
    with subscription as entered:
        assert entered is subscription


def test_subscription_exit_removes() -> None:
    handler = EventHandler(print)
    remove_func = Mock(return_value=True)
    with Subscription("my_event", handler, remove_func):
        pass
    remove_func.assert_called_once_with("my_event", handler)


def test_subscription_exit_removes_when_block_raises() -> None:
    remove_func = Mock(return_value=True)
    with (
        pytest.raises(RuntimeError, match=r"handler failed"),
        Subscription("my_event", EventHandler(print), remove_func),
    ):
        failing_handler()
    remove_func.assert_called_once()
