from __future__ import annotations

import pytest

from minevent import EventHandler, EventManager, Subscription


def failing_handler() -> None:
    msg = "handler failed"
    raise RuntimeError(msg)


##################################
#     Tests for Subscription     #
##################################


def test_subscription_repr() -> None:
    assert repr(Subscription(EventManager(), "my_event", EventHandler(print))) == (
        "Subscription(event='my_event')"
    )


def test_subscription_event() -> None:
    assert Subscription(EventManager(), "my_event", EventHandler(print)).event == "my_event"


def test_subscription_event_handler() -> None:
    handler = EventHandler(print)
    assert Subscription(EventManager(), "my_event", handler).event_handler is handler


def test_subscription_once_default() -> None:
    assert not Subscription(EventManager(), "my_event", EventHandler(print)).once


def test_subscription_once_true() -> None:
    assert Subscription(EventManager(), "my_event", EventHandler(print), once=True).once


def test_subscription_active_after_add() -> None:
    assert EventManager().add_event_handler("my_event", EventHandler(print)).active


def test_subscription_remove_returns_true() -> None:
    assert EventManager().add_event_handler("my_event", EventHandler(print)).remove()


def test_subscription_remove_twice_returns_false() -> None:
    subscription = EventManager().add_event_handler("my_event", EventHandler(print))
    subscription.remove()
    assert not subscription.remove()


def test_subscription_remove_inactive_after_remove() -> None:
    subscription = EventManager().add_event_handler("my_event", EventHandler(print))
    subscription.remove()
    assert not subscription.active


def test_subscription_remove_removes_from_manager() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", EventHandler(print)).remove()
    assert len(manager) == 0


def test_subscription_remove_same_handler_registered_twice_keeps_other_registration() -> None:
    manager = EventManager()
    handler = EventHandler(print)
    first = manager.add_event_handler("my_event", handler)
    manager.add_event_handler("my_event", handler)
    first.remove()
    first.remove()
    assert len(manager) == 1


def test_subscription_remove_same_handler_registered_twice_second_stays_active() -> None:
    manager = EventManager()
    handler = EventHandler(print)
    first = manager.add_event_handler("my_event", handler)
    second = manager.add_event_handler("my_event", handler)
    first.remove()
    first.remove()
    assert second.active


def test_subscription_inactive_after_clear_event() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(print))
    manager.clear_event("my_event")
    assert not subscription.active


def test_subscription_remove_after_clear_event_returns_false() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(print))
    manager.clear_event("my_event")
    assert not subscription.remove()


def test_subscription_inactive_after_reset() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", EventHandler(print))
    manager.reset()
    assert not subscription.active


def test_subscription_enter_returns_subscription() -> None:
    subscription = EventManager().add_event_handler("my_event", EventHandler(print))
    with subscription as entered:
        assert entered is subscription


def test_subscription_exit_removes() -> None:
    manager = EventManager()
    with manager.add_event_handler("my_event", EventHandler(print)):
        pass
    assert len(manager) == 0


def test_subscription_exit_removes_when_block_raises() -> None:
    manager = EventManager()
    with (
        pytest.raises(RuntimeError, match=r"handler failed"),
        manager.add_event_handler("my_event", EventHandler(print)),
    ):
        failing_handler()
    assert len(manager) == 0
