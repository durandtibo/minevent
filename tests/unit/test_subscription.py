from __future__ import annotations

from unittest.mock import Mock

from minevent import EventHandler, Subscription

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
