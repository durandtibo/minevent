from __future__ import annotations

import copy
import pickle
import threading
from enum import Enum, StrEnum
from typing import TYPE_CHECKING, Any

import pytest

from minevent import (
    Context,
    EventManager,
    Subscription,
)
from minevent.manager import _check_event
from tests.unit.handlers import (
    hello_handler,
    noop_handler,
    payload_handler,
)
from tests.unit.utils import INVALID_EVENTS

if TYPE_CHECKING:
    from collections.abc import Callable


def lock_is_held(manager: EventManager) -> bool:
    r"""Indicate if the lock of the manager is held by the current
    thread."""
    acquired: list[bool] = []

    def try_acquire() -> None:
        acquired.append(manager._lock.acquire(blocking=False))
        if acquired[0]:
            manager._lock.release()

    thread = threading.Thread(target=try_acquire)
    thread.start()
    thread.join()
    return not acquired[0]


class StrEvent(StrEnum):
    r"""Implement event names that are strings."""

    EPOCH_END = "epoch_end"


class PlainEvent(Enum):
    r"""Implement event names with ``str`` values that are not
    strings."""

    EPOCH_END = "epoch_end"


class LockRecorder:
    r"""Implement a handler whose finalizer records if the lock of the
    manager is held."""

    def __init__(self, manager: EventManager, lock_held: list[bool]) -> None:
        self._manager = manager
        self._lock_held = lock_held

    def __del__(self) -> None:
        self._lock_held.append(lock_is_held(self._manager))

    def __call__(self, _: Context) -> bool:
        r"""Implement a handler, or a condition that is ``True``."""
        return True


##################################
#     Tests for EventManager     #
##################################


def test_event_manager_str_without_event_handler() -> None:
    assert str(EventManager()).startswith("EventManager(")


def test_event_manager_str_with_event_handler() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", hello_handler)
    assert str(event_manager).startswith("EventManager(")


def test_event_manager_reset() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", hello_handler)
    event_manager.add_event_handler("my_other_event", hello_handler)
    event_manager.reset()
    assert event_manager.events == []


def test_event_manager_reset_empty() -> None:
    event_manager = EventManager()
    event_manager.reset()
    assert event_manager.events == []


def test_event_manager_repr_empty() -> None:
    assert repr(EventManager()) == "EventManager(events={})"


def test_event_manager_repr_with_event_handlers() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", hello_handler)
    event_manager.add_event_handler("my_event", hello_handler)
    event_manager.add_event_handler("my_other_event", hello_handler)
    assert repr(event_manager) == "EventManager(events={'my_event': 2, 'my_other_event': 1})"


def test_event_manager_events_empty() -> None:
    assert EventManager().events == []


def test_event_manager_events() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", hello_handler)
    event_manager.add_event_handler("my_other_event", hello_handler)
    event_manager.trigger_event("unknown_event")
    assert event_manager.events == ["my_event", "my_other_event"]


def test_event_manager_contains_false_empty() -> None:
    assert "my_event" not in EventManager()


def test_event_manager_contains_non_str() -> None:
    manager = EventManager()
    manager.add_event_handler("1", noop_handler)
    assert 1 not in manager


def test_event_manager_str_enum_event_is_kept_as_given() -> None:
    manager = EventManager()
    manager.add_event_handler(StrEvent.EPOCH_END, noop_handler)
    assert manager.events[0] is StrEvent.EPOCH_END


def test_event_manager_str_enum_event_matches_its_value() -> None:
    manager = EventManager()
    manager.add_event_handler(StrEvent.EPOCH_END, hello_handler)
    manager.trigger_event("epoch_end")
    assert hello_handler.call_count == 1


def test_event_manager_plain_enum_event_is_rejected() -> None:
    event: Any = PlainEvent.EPOCH_END
    with pytest.raises(TypeError, match=r"^event must be a str, but got PlainEvent$"):
        EventManager().add_event_handler(event, noop_handler)


def test_event_manager_contains_true() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", hello_handler)
    assert "my_event" in event_manager


def test_event_manager_contains_false_after_remove() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", hello_handler).remove()
    assert "my_event" not in event_manager


def test_event_manager_clear_event() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", hello_handler)
    event_manager.add_event_handler("my_event", hello_handler)
    event_manager.add_event_handler("my_other_event", hello_handler)
    event_manager.clear_event("my_event")
    assert event_manager.events == ["my_other_event"]


def test_event_manager_clear_event_handlers_do_not_run() -> None:
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", hello_handler)
    event_manager.clear_event("my_event")
    event_manager.trigger_event("my_event")
    assert hello_handler.call_count == 0


def test_event_manager_clear_event_missing() -> None:
    manager = EventManager()
    manager.clear_event("my_event")
    assert manager.events == []


def test_event_manager_clear_event_must_be_str() -> None:
    event: Any = 1
    with pytest.raises(TypeError, match=r"event must be a str"):
        EventManager().clear_event(event)


########################################
#     Tests for user code and lock     #
########################################


def test_event_manager_trigger_event_runs_handler_without_lock() -> None:
    manager = EventManager()
    lock_held: list[bool] = []
    manager.add_event_handler("my_event", lambda _: lock_held.append(lock_is_held(manager)))
    manager.trigger_event("my_event")
    assert lock_held == [False]


def test_event_manager_clear_event_releases_handlers_without_lock() -> None:
    manager = EventManager()
    lock_held: list[bool] = []
    manager.add_event_handler("my_event", LockRecorder(manager, lock_held))
    manager.add_event_handler("my_event", LockRecorder(manager, lock_held))
    manager.clear_event("my_event")
    assert lock_held == [False, False]


def test_event_manager_reset_releases_handlers_without_lock() -> None:
    manager = EventManager()
    lock_held: list[bool] = []
    manager.add_event_handler("my_event", LockRecorder(manager, lock_held))
    manager.add_event_handler("my_other_event", LockRecorder(manager, lock_held))
    manager.reset()
    assert lock_held == [False, False]


def test_event_manager_clear_event_releases_conditions_without_lock() -> None:
    manager = EventManager()
    lock_held: list[bool] = []
    manager.add_event_handler("my_event", noop_handler, condition=LockRecorder(manager, lock_held))
    manager.add_event_handler("my_event", noop_handler, condition=LockRecorder(manager, lock_held))
    manager.clear_event("my_event")
    assert lock_held == [False, False]


def test_event_manager_remove_releases_handler_without_lock() -> None:
    manager = EventManager()
    lock_held: list[bool] = []
    manager.add_event_handler("my_event", LockRecorder(manager, lock_held)).remove()
    assert lock_held == [False]


def test_event_manager_reset_keeps_working() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", noop_handler)
    manager.reset()
    manager.add_event_handler("my_event", hello_handler)
    manager.trigger_event("my_event")
    assert hello_handler.call_count == 1


#################################################
#     Tests for truthiness, copy and pickle     #
#################################################


def test_event_manager_bool_empty() -> None:
    assert bool(EventManager()) is True


def test_event_manager_bool_with_registration() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler)
    assert bool(manager) is True


def test_event_manager_has_no_len() -> None:
    manager: Any = EventManager()
    with pytest.raises(TypeError, match=r"object of type 'EventManager' has no len\(\)"):
        len(manager)


def test_event_manager_empty_manager_or_default_keeps_manager() -> None:
    manager = EventManager()
    assert (manager or EventManager()) is manager


@pytest.mark.parametrize("func", [copy.copy, copy.deepcopy, pickle.dumps])
def test_event_manager_copy_and_pickle_raise_type_error(func: Callable[[object], object]) -> None:
    with pytest.raises(TypeError, match=r"EventManager cannot be copied or pickled"):
        func(EventManager())


def test_event_manager_copy_subclass_names_subclass() -> None:
    class MyManager(EventManager):
        pass

    with pytest.raises(TypeError, match=r"MyManager cannot be copied or pickled"):
        copy.copy(MyManager())


#######################################
#     Tests for get_subscriptions     #
#######################################


def test_event_manager_get_subscriptions_empty() -> None:
    assert EventManager().get_subscriptions("my_event") == ()


def test_event_manager_get_subscriptions_does_not_create_event() -> None:
    manager = EventManager()
    manager.get_subscriptions("my_event")
    assert "my_event" not in manager


def test_event_manager_get_subscriptions_keeps_order() -> None:
    manager = EventManager()
    first = manager.add_event_handler("my_event", hello_handler)
    second = manager.add_event_handler("my_event", payload_handler)
    assert manager.get_subscriptions("my_event") == (first, second)


def test_event_manager_get_subscriptions_only_requested_event() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", hello_handler)
    manager.add_event_handler("my_other_event", payload_handler)
    assert manager.get_subscriptions("my_event") == (subscription,)


def test_event_manager_get_subscriptions_is_a_snapshot() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", hello_handler)
    subscriptions = manager.get_subscriptions("my_event")
    manager.add_event_handler("my_event", payload_handler)
    assert subscriptions == (subscription,)


@pytest.mark.parametrize("event", INVALID_EVENTS)
def test_event_manager_get_subscriptions_event_must_be_str(event: Any) -> None:
    with pytest.raises(TypeError, match=r"event must be a str"):
        EventManager().get_subscriptions(event)


def test_event_manager_get_subscriptions_event_handler() -> None:
    manager = EventManager()
    handler = hello_handler
    manager.add_event_handler("my_event", handler, once=True)
    assert manager.get_subscriptions("my_event")[0].handler is handler


##################################
#     Tests for _check_event     #
##################################


@pytest.mark.parametrize("event", ["my_event", ""])
def test_check_event_accepts_str(event: str) -> None:
    assert _check_event(event) is None


@pytest.mark.parametrize("event", [1, None, b"e"])
def test_check_event_rejects_non_str(event: object) -> None:
    with pytest.raises(TypeError, match=r"event must be a str, but got"):
        _check_event(event)


def test_check_event_error_names_the_type() -> None:
    with pytest.raises(TypeError, match=r"but got bytes"):
        _check_event(b"e")


#############################
#     Tests for _remove     #
#############################


def test_remove_removes_the_registration() -> None:
    manager = EventManager()
    first = manager.add_event_handler("my_event", noop_handler)
    second = manager.add_event_handler("my_event", noop_handler)
    manager._remove(first)
    assert manager.get_subscriptions("my_event") == (second,)


def test_remove_returns_true() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", noop_handler)
    assert manager._remove(subscription)


def test_remove_deactivates_the_registration() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", noop_handler)
    manager._remove(subscription)
    assert not subscription.active


def test_remove_already_removed_returns_false() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", noop_handler)
    manager._remove(subscription)
    assert not manager._remove(subscription)


def test_remove_already_removed_keeps_the_other_registrations() -> None:
    manager = EventManager()
    first = manager.add_event_handler("my_event", noop_handler)
    second = manager.add_event_handler("my_event", noop_handler)
    manager._remove(first)
    manager._remove(first)
    assert manager.get_subscriptions("my_event") == (second,)


def test_remove_last_registration_drops_the_event() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", noop_handler)
    manager._remove(subscription)
    assert manager.events == []


def test_remove_keeps_the_other_events() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", noop_handler)
    manager.add_event_handler("my_other_event", noop_handler)
    manager._remove(subscription)
    assert manager.events == ["my_other_event"]


def test_remove_unknown_event_returns_false() -> None:
    subscription = Subscription(EventManager(), "my_event", noop_handler)
    assert not EventManager()._remove(subscription)


def test_remove_never_registered_stays_inactive() -> None:
    manager = EventManager()
    subscription = Subscription(manager, "my_event", noop_handler)
    manager._remove(subscription)
    assert not subscription.active
