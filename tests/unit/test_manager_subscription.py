from __future__ import annotations

import functools
import inspect
import logging
from typing import Any
from unittest.mock import create_autospec

import pytest

from minevent import (
    Context,
    EventManager,
    PeriodicCondition,
    Subscription,
)
from tests.unit.handlers import (
    AwaitableResult,
    BadReprCallable,
    CallableRecorder,
    async_condition,
    copy_context,
    has_payload,
    hello_handler,
    noop_handler,
)

logger = logging.getLogger(__name__)


def read_secret(secret: str) -> None:
    r"""Implement a handler that needs a bound argument."""


def failing_handler() -> None:
    msg = "handler failed"
    raise RuntimeError(msg)


class AsyncConditionObject:
    r"""Implement a condition with an async ``__call__``."""

    async def __call__(self) -> bool:
        return False


def condition_returning_a_coroutine() -> object:
    r"""Implement a synchronous condition that returns a coroutine."""
    return async_condition()


def condition_of_context_returning_a_coroutine(context: Context) -> object:
    r"""Implement a synchronous condition of the context that returns a
    coroutine."""
    logger.info("context %s", context)
    return async_condition()


def flag_and_registry(manager: EventManager, subscription: Subscription) -> tuple[bool, bool]:
    r"""Gets the flag of a registration and its presence in the
    manager."""
    return subscription.active, subscription in manager.get_subscriptions(subscription.event)


##################################
#     Tests for Subscription     #
##################################


def test_subscription_repr() -> None:
    assert repr(Subscription(EventManager(), "my_event", noop_handler)) == (
        "Subscription(event='my_event', handler='noop_handler')"
    )


def test_subscription_repr_names_function_of_partial() -> None:
    subscription = Subscription(
        EventManager(), "my_event", functools.partial(read_secret, "secret")
    )
    assert repr(subscription) == "Subscription(event='my_event', handler='read_secret')"


def test_subscription_repr_names_class_of_callable_object() -> None:
    subscription = Subscription(EventManager(), "my_event", CallableRecorder([]))
    assert repr(subscription) == "Subscription(event='my_event', handler='CallableRecorder')"


def test_subscription_repr_ignores_repr_of_handler() -> None:
    assert repr(Subscription(EventManager(), "my_event", BadReprCallable())) == (
        "Subscription(event='my_event', handler='BadReprCallable')"
    )


def test_event_manager_get_subscriptions_repr_names_handlers() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", noop_handler)
    manager.add_event_handler("my_event", hello_handler)
    assert repr(manager.get_subscriptions("my_event")) == (
        "(Subscription(event='my_event', handler='noop_handler'), "
        "Subscription(event='my_event', handler='hello_handler'))"
    )


def test_subscription_event() -> None:
    assert Subscription(EventManager(), "my_event", noop_handler).event == "my_event"


def test_subscription_handler() -> None:
    handler = noop_handler
    assert Subscription(EventManager(), "my_event", handler).handler is handler


def test_subscription_once_default() -> None:
    assert not Subscription(EventManager(), "my_event", noop_handler).once


def test_subscription_once_true() -> None:
    assert Subscription(EventManager(), "my_event", noop_handler, once=True).once


def test_subscription_condition_default() -> None:
    assert Subscription(EventManager(), "my_event", noop_handler).condition is None


def test_subscription_condition() -> None:
    condition = PeriodicCondition(freq=2)
    assert Subscription(
        EventManager(), "my_event", noop_handler, condition=condition
    ).condition is (condition)


def test_subscription_call_returns_handler_result() -> None:
    context = Context({"a": 1})
    assert (
        Subscription(EventManager(), "my_event", lambda context: context)._call(context) is context
    )


def test_subscription_call_removed_returns_none() -> None:
    subscription = EventManager().add_event_handler("my_event", hello_handler)
    subscription.remove()
    assert subscription._call(Context()) is None


def test_subscription_call_removed_does_not_call_handler() -> None:
    subscription = EventManager().add_event_handler("my_event", hello_handler)
    subscription.remove()
    subscription._call(Context())
    assert hello_handler.call_count == 0


def test_subscription_call_removed_does_not_evaluate_condition() -> None:
    condition = create_autospec(has_payload, return_value=True)
    subscription = EventManager().add_event_handler("my_event", hello_handler, condition=condition)
    subscription.remove()
    subscription._call(Context())
    assert condition.call_count == 0


def test_subscription_call_condition_false_returns_none() -> None:
    subscription = Subscription(EventManager(), "my_event", lambda: 1, condition=lambda: False)
    assert subscription._call(Context()) is None


def test_subscription_call_condition_false_does_not_call_handler() -> None:
    subscription = Subscription(EventManager(), "my_event", hello_handler, condition=lambda: False)
    subscription._call(Context())
    assert hello_handler.call_count == 0


def test_subscription_call_condition_true_calls_handler() -> None:
    subscription = Subscription(EventManager(), "my_event", lambda: 1, condition=lambda: True)
    assert subscription._call(Context()) == 1


def test_subscription_call_condition_without_parameter_is_called_without_argument() -> None:
    subscription = Subscription(EventManager(), "my_event", lambda: 1, condition=lambda: True)
    assert subscription._call(Context({"a": 1})) == 1


def test_subscription_call_condition_with_parameter_receives_the_context() -> None:
    contexts: list[Context] = []

    def condition(context: Context) -> bool:
        contexts.append(context)
        return True

    context = Context({"a": 1})
    Subscription(EventManager(), "my_event", hello_handler, condition=condition)._call(context)
    assert contexts == [context]


def test_subscription_call_condition_with_parameter_true_calls_handler() -> None:
    subscription = Subscription(
        EventManager(), "my_event", lambda: 1, condition=lambda context: context["a"] == 1
    )
    assert subscription._call(Context({"a": 1})) == 1


def test_subscription_call_condition_with_parameter_false_returns_none() -> None:
    subscription = Subscription(
        EventManager(), "my_event", lambda: 1, condition=lambda context: context["a"] == 2
    )
    assert subscription._call(Context({"a": 1})) is None


def test_subscription_call_condition_with_parameter_false_does_not_call_handler() -> None:
    Subscription(
        EventManager(), "my_event", hello_handler, condition=lambda context: context["a"] == 2
    )._call(Context({"a": 1}))
    assert hello_handler.call_count == 0


def test_subscription_call_condition_with_parameter_and_handler_with_parameter() -> None:
    subscription = Subscription(
        EventManager(), "my_event", copy_context, condition=lambda context: "a" in context
    )
    assert subscription._call(Context({"a": 1})) == {"a": 1}


def test_subscription_call_condition_with_parameter_does_not_consume_once() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler(
        "my_event", hello_handler, once=True, condition=lambda context: context["go"]
    )
    subscription._call(Context({"go": False}))
    assert subscription.active


def test_subscription_call_condition_with_parameter_raises() -> None:
    subscription = Subscription(
        EventManager(), "my_event", hello_handler, condition=lambda context: context["missing"]
    )
    with pytest.raises(KeyError, match=r"key 'missing' not found in the context"):
        subscription._call(Context({"a": 1}))


def test_subscription_call_condition_is_called_once() -> None:
    condition = create_autospec(has_payload, return_value=True)
    Subscription(EventManager(), "my_event", hello_handler, condition=condition)._call(Context())
    assert condition.call_count == 1


@pytest.mark.parametrize(
    "condition",
    [
        async_condition,
        AsyncConditionObject(),
        condition_returning_a_coroutine,
        condition_of_context_returning_a_coroutine,
        AwaitableResult,
    ],
)
def test_subscription_call_condition_returns_awaitable(condition: Any) -> None:
    subscription = Subscription(EventManager(), "my_event", hello_handler, condition=condition)
    with pytest.raises(TypeError, match=r"^condition .+ returned an awaitable$"):
        subscription._call(Context())
    assert hello_handler.call_count == 0


def test_subscription_call_condition_returns_awaitable_closes_the_coroutine() -> None:
    coroutine = async_condition()

    def condition() -> Any:
        return coroutine

    subscription = Subscription(EventManager(), "my_event", hello_handler, condition=condition)
    with pytest.raises(TypeError, match=r"returned an awaitable"):
        subscription._call(Context())
    assert inspect.getcoroutinestate(coroutine) == inspect.CORO_CLOSED


@pytest.mark.parametrize("result", [1, "yes", [0]])
def test_subscription_call_condition_truthy_non_bool(result: Any) -> None:
    subscription = Subscription(EventManager(), "my_event", lambda: 2, condition=lambda: result)
    assert subscription._call(Context()) == 2


@pytest.mark.parametrize("result", [0, "", [], None])
def test_subscription_call_condition_falsy_non_bool(result: Any) -> None:
    subscription = Subscription(EventManager(), "my_event", lambda: 2, condition=lambda: result)
    assert subscription._call(Context()) is None


def test_subscription_options_are_keyword_only() -> None:
    args: list[Any] = [EventManager(), "my_event", noop_handler, True]
    with pytest.raises(TypeError, match=r"positional arguments"):
        Subscription(*args)


def test_subscription_call_once_removes_registration() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", hello_handler, once=True)
    subscription._call(Context())
    assert not subscription.active


def test_subscription_call_once_calls_handler() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", lambda: 1, once=True)
    assert manager.get_subscriptions("my_event")[0]._call(Context()) == 1


def test_subscription_call_once_lost_claim_returns_none() -> None:
    manager = EventManager()
    subscriptions: list[Subscription] = []

    def condition() -> bool:
        subscriptions[0].remove()  # another thread wins the claim after the check
        return True

    subscriptions.append(
        manager.add_event_handler("my_event", lambda: 1, condition=condition, once=True)
    )
    assert subscriptions[0]._call(Context()) is None


def test_subscription_call_once_lost_claim_does_not_call_handler() -> None:
    manager = EventManager()
    subscriptions: list[Subscription] = []

    def condition() -> bool:
        subscriptions[0].remove()
        return True

    subscriptions.append(
        manager.add_event_handler("my_event", hello_handler, condition=condition, once=True)
    )
    subscriptions[0]._call(Context())
    assert hello_handler.call_count == 0


def test_subscription_call_once_removed_does_not_call_handler() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", hello_handler, once=True)
    subscription.remove()
    subscription._call(Context())
    assert hello_handler.call_count == 0


def test_subscription_call_not_once_keeps_registration() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", hello_handler)
    subscription._call(Context())
    assert subscription.active


def test_subscription_call_passes_the_whole_context() -> None:
    subscription = Subscription(EventManager(), "my_event", copy_context)
    assert subscription._call(Context({"a": 1, "b": 2})) == {"a": 1, "b": 2}


def test_subscription_call_without_parameter_calls_handler_without_argument() -> None:
    subscription = Subscription(EventManager(), "my_event", lambda: "called")
    assert subscription._call(Context({"a": 1})) == "called"


def test_subscription_rejected_signature() -> None:
    with pytest.raises(TypeError, match=r"^handler print must need no argument"):
        Subscription(EventManager(), "my_event", print)


def test_subscription_active_after_add() -> None:
    assert EventManager().add_event_handler("my_event", noop_handler).active


def test_subscription_active_never_registered() -> None:
    assert Subscription(EventManager(), "my_event", noop_handler).active


def test_subscription_active_false_after_remove() -> None:
    subscription = EventManager().add_event_handler("my_event", noop_handler)
    subscription.remove()
    assert not subscription.active


def test_subscription_active_other_subscription_removed() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", noop_handler).remove()
    assert manager.add_event_handler("my_event", noop_handler).active


def test_subscription_active_other_event_cleared() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", noop_handler)
    manager.clear_event("my_other_event")
    assert subscription.active


def test_subscription_remove_returns_true() -> None:
    assert EventManager().add_event_handler("my_event", noop_handler).remove()


def test_subscription_remove_twice_returns_false() -> None:
    subscription = EventManager().add_event_handler("my_event", noop_handler)
    subscription.remove()
    assert not subscription.remove()


def test_subscription_remove_inactive_after_remove() -> None:
    subscription = EventManager().add_event_handler("my_event", noop_handler)
    subscription.remove()
    assert not subscription.active


def test_subscription_remove_removes_from_manager() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", noop_handler).remove()
    assert len(manager) == 0


def test_subscription_remove_middle_keeps_order() -> None:
    manager = EventManager()
    first = manager.add_event_handler("my_event", noop_handler)
    second = manager.add_event_handler("my_event", noop_handler)
    third = manager.add_event_handler("my_event", noop_handler)
    second.remove()
    assert manager.get_subscriptions("my_event") == (first, third)


def test_subscription_remove_first_and_last_keeps_middle() -> None:
    manager = EventManager()
    first = manager.add_event_handler("my_event", noop_handler)
    second = manager.add_event_handler("my_event", noop_handler)
    third = manager.add_event_handler("my_event", noop_handler)
    first.remove()
    third.remove()
    assert manager.get_subscriptions("my_event") == (second,)


def test_subscription_remove_same_handler_registered_three_times_removes_second() -> None:
    manager = EventManager()
    handler = noop_handler
    first = manager.add_event_handler("my_event", handler)
    second = manager.add_event_handler("my_event", handler)
    third = manager.add_event_handler("my_event", handler)
    second.remove()
    assert manager.get_subscriptions("my_event") == (first, third)


def test_subscription_remove_not_registered_returns_false() -> None:
    subscription = Subscription(EventManager(), "my_event", noop_handler)
    assert not subscription.remove()


def test_subscription_remove_not_registered_keeps_other_registration() -> None:
    manager = EventManager()
    registered = manager.add_event_handler("my_event", noop_handler)
    Subscription(manager, "my_event", noop_handler).remove()
    assert manager.get_subscriptions("my_event") == (registered,)


def test_subscription_is_hashable_by_identity() -> None:
    manager = EventManager()
    handler = noop_handler
    first = manager.add_event_handler("my_event", handler)
    second = manager.add_event_handler("my_event", handler)
    assert len({first, second}) == 2


def test_subscription_remove_same_handler_registered_twice_keeps_other_registration() -> None:
    manager = EventManager()
    handler = noop_handler
    first = manager.add_event_handler("my_event", handler)
    manager.add_event_handler("my_event", handler)
    first.remove()
    first.remove()
    assert len(manager) == 1


def test_subscription_remove_same_handler_registered_twice_second_stays_active() -> None:
    manager = EventManager()
    handler = noop_handler
    first = manager.add_event_handler("my_event", handler)
    second = manager.add_event_handler("my_event", handler)
    first.remove()
    first.remove()
    assert second.active


def test_subscription_inactive_after_clear_event() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", noop_handler)
    manager.clear_event("my_event")
    assert not subscription.active


def test_subscription_remove_after_clear_event_returns_false() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", noop_handler)
    manager.clear_event("my_event")
    assert not subscription.remove()


def test_subscription_inactive_after_reset() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", noop_handler)
    manager.reset()
    assert not subscription.active


def test_subscription_enter_returns_subscription() -> None:
    subscription = EventManager().add_event_handler("my_event", noop_handler)
    with subscription as entered:
        assert entered is subscription


def test_subscription_exit_removes() -> None:
    manager = EventManager()
    with manager.add_event_handler("my_event", noop_handler):
        pass
    assert len(manager) == 0


def test_subscription_exit_does_not_swallow_exception_of_block() -> None:
    with (
        pytest.raises(RuntimeError, match=r"handler failed"),
        EventManager().add_event_handler("my_event", noop_handler),
    ):
        failing_handler()


def test_subscription_exit_removes_when_block_raises() -> None:
    manager = EventManager()
    with (
        pytest.raises(RuntimeError, match=r"handler failed"),
        manager.add_event_handler("my_event", noop_handler),
    ):
        failing_handler()
    assert len(manager) == 0


###############################################
#     Tests for the flag and the registry     #
###############################################


def test_flag_and_registry_agree_before_removal() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", noop_handler)
    assert flag_and_registry(manager, subscription) == (True, True)


def test_flag_and_registry_agree_after_remove() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", noop_handler)
    subscription.remove()
    assert flag_and_registry(manager, subscription) == (False, False)


def test_flag_and_registry_agree_after_exit() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", noop_handler)
    with subscription:
        pass
    assert flag_and_registry(manager, subscription) == (False, False)


def test_flag_and_registry_agree_after_clear_event() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", noop_handler)
    manager.clear_event("my_event")
    assert flag_and_registry(manager, subscription) == (False, False)


def test_flag_and_registry_agree_after_reset() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", noop_handler)
    manager.reset()
    assert flag_and_registry(manager, subscription) == (False, False)


def test_flag_and_registry_agree_after_clear_other_event() -> None:
    manager = EventManager()
    subscription = manager.add_event_handler("my_event", noop_handler)
    manager.clear_event("other_event")
    assert flag_and_registry(manager, subscription) == (True, True)
