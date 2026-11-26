from __future__ import annotations

import functools
import inspect
import logging
from typing import TYPE_CHECKING, Any
from unittest.mock import create_autospec

import pytest

from minevent import (
    Context,
    EventManager,
    PeriodicCondition,
    Subscription,
)
from tests.unit.handlers import (
    AsyncConditionMethod,
    AsyncConditionObject,
    AwaitableResult,
    BadReprCallable,
    CallableRecorder,
    async_condition,
    condition_returning_a_coroutine,
    fail,
    has_payload,
    hello_handler,
    noop_handler,
)
from tests.unit.utils import raised

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


def read_secret(secret: str) -> None:
    r"""Implement a handler that needs a bound argument."""


def failing_handler() -> None:
    r"""Implement a handler that raises a ``RuntimeError``."""
    msg = "handler failed"
    raise RuntimeError(msg)


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


def test_subscription_options_are_keyword_only() -> None:
    args: list[Any] = [EventManager(), "my_event", noop_handler, True]
    with pytest.raises(TypeError, match=r"positional arguments"):
        Subscription(*args)


@pytest.mark.parametrize(
    "condition",
    [async_condition, AsyncConditionMethod().check, functools.partial(async_condition)],
)
def test_subscription_async_condition(condition: Any) -> None:
    with pytest.raises(TypeError, match=r"^condition must be synchronous, but got "):
        Subscription(EventManager(), "my_event", noop_handler, condition=condition)


def test_subscription_async_condition_with_parameter() -> None:
    async def is_late(context: Context) -> bool:
        return bool(context)

    condition: Any = is_late
    with pytest.raises(TypeError, match=r"^condition must be synchronous, but got .*is_late$"):
        Subscription(EventManager(), "my_event", noop_handler, condition=condition)


def test_subscription_async_condition_rejected_signature_first() -> None:
    async def condition(first: int, second: int) -> bool:
        return first < second

    condition_any: Any = condition
    with pytest.raises(TypeError, match=r"must need no argument or only the context"):
        Subscription(EventManager(), "my_event", noop_handler, condition=condition_any)


@pytest.mark.parametrize("condition", [AsyncConditionObject(), condition_returning_a_coroutine])
def test_subscription_condition_that_returns_a_coroutine_is_accepted(condition: Any) -> None:
    subscription = Subscription(EventManager(), "my_event", noop_handler, condition=condition)
    assert subscription.condition is condition


def test_subscription_async_handler_is_accepted() -> None:
    subscription = Subscription(EventManager(), "my_event", async_condition)
    assert subscription.handler is async_condition


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


############################
#     Tests for _claim     #
############################


def subscribe(handler: Callable[..., object] = noop_handler, **kwargs: Any) -> Subscription:
    r"""Register ``handler`` to ``my_event`` of a new manager."""
    return EventManager().add_event_handler("my_event", handler, **kwargs)


def subscribe_removed_by_its_condition(*, once: bool) -> Subscription:
    r"""Register a handler whose condition removes the registration and
    returns ``True``."""
    manager = EventManager()

    def condition() -> bool:
        return manager.get_subscriptions("my_event")[0].remove()

    return manager.add_event_handler("my_event", noop_handler, once=once, condition=condition)


def test_claim_without_option() -> None:
    assert subscribe()._claim(Context())


def test_claim_without_option_keeps_registration() -> None:
    subscription = subscribe()
    subscription._claim(Context())
    assert subscription.active


def test_claim_does_not_call_the_handler() -> None:
    subscribe(hello_handler, once=True, condition=lambda: True)._claim(Context())
    assert hello_handler.call_count == 0


def test_claim_once() -> None:
    assert subscribe(once=True)._claim(Context())


def test_claim_once_removes_registration() -> None:
    subscription = subscribe(once=True)
    subscription._claim(Context())
    assert not subscription.active


def test_claim_once_second_time() -> None:
    subscription = subscribe(once=True)
    subscription._claim(Context())
    assert not subscription._claim(Context())


@pytest.mark.parametrize("once", [True, False])
def test_claim_condition_removes_registration(once: bool) -> None:
    subscription = subscribe_removed_by_its_condition(once=once)
    assert not subscription._claim(Context())


def test_claim_removed_registration_with_condition() -> None:
    subscription = subscribe(condition=lambda: True)
    subscription.remove()
    assert not subscription._claim(Context())


@pytest.mark.parametrize("result", [True, 1, "yes", [0]])
def test_claim_condition_truthy(result: Any) -> None:
    assert subscribe(condition=lambda: result)._claim(Context())


@pytest.mark.parametrize("result", [False, 0, "", [], None])
def test_claim_condition_falsy(result: Any) -> None:
    assert not subscribe(condition=lambda: result)._claim(Context())


def test_claim_condition_false_does_not_consume_once() -> None:
    subscription = subscribe(once=True, condition=lambda: False)
    subscription._claim(Context())
    assert subscription.active


def test_claim_condition_without_parameter() -> None:
    condition = create_autospec(noop_handler, return_value=True)
    subscribe(condition=condition)._claim(Context({"a": 1}))
    condition.assert_called_once_with()


def test_claim_condition_with_parameter_receives_the_context() -> None:
    condition = create_autospec(has_payload, return_value=True)
    subscribe(condition=condition)._claim(Context({"a": 1}))
    condition.assert_called_once_with({"a": 1})


def test_claim_condition_raises() -> None:
    subscription = subscribe(condition=lambda context: context["missing"])
    with pytest.raises(KeyError, match=r"key 'missing' not found in the context"):
        subscription._claim(Context({"a": 1}))


def test_claim_condition_raises_keeps_once_registration() -> None:
    subscription = subscribe(once=True, condition=lambda context: context["missing"])
    with pytest.raises(KeyError, match=r"key 'missing' not found in the context"):
        subscription._claim(Context())
    assert subscription.active


def test_claim_condition_raises_note_names_condition_and_handler() -> None:
    def is_late(context: Context) -> bool:
        return context["missing"]

    subscription = subscribe(functools.partial(read_secret, "secret"), condition=is_late)
    assert raised(subscription._claim, Context()).__notes__ == [
        (
            f"raised by the condition {is_late.__qualname__} of read_secret "
            "while handling the event 'my_event'"
        )
    ]


def test_claim_condition_note_names_function_of_partial() -> None:
    subscription = subscribe(condition=functools.partial(fail))
    assert raised(subscription._claim, Context()).__notes__ == [
        "raised by the condition fail of noop_handler while handling the event 'my_event'"
    ]


def test_claim_condition_note_ignores_repr_of_condition() -> None:
    class BadReprCondition(BadReprCallable):
        def __call__(self) -> None:
            fail()

    subscription = subscribe(condition=BadReprCondition())
    assert (
        raised(subscription._claim, Context())
        .__notes__[0]
        .startswith(f"raised by the condition {BadReprCondition.__qualname__} of noop_handler ")
    )


def test_claim_condition_bool_raises_has_note() -> None:
    class Ambiguous:
        def __bool__(self) -> bool:
            msg = "ambiguous truth value"
            raise ValueError(msg)

    subscription = subscribe(condition=Ambiguous)
    assert (
        raised(subscription._claim, Context()).__notes__[0].startswith("raised by the condition ")
    )


def test_claim_condition_base_exception_has_no_note() -> None:
    condition = create_autospec(noop_handler, side_effect=KeyboardInterrupt("interrupted"))
    subscription = subscribe(condition=condition)
    assert not hasattr(raised(subscription._claim, Context()), "__notes__")


@pytest.mark.parametrize(
    "condition",
    [
        AsyncConditionObject(),
        condition_returning_a_coroutine,
        condition_of_context_returning_a_coroutine,
        AwaitableResult,
    ],
)
def test_claim_condition_returns_awaitable(condition: Any) -> None:
    subscription = subscribe(condition=condition)
    with pytest.raises(TypeError, match=r"^condition .+ returned an awaitable"):
        subscription._claim(Context())


def test_claim_condition_returns_awaitable_names_the_condition_without_parameter() -> None:
    subscription = subscribe(condition=AwaitableResult)
    with pytest.raises(TypeError, match=r"^condition AwaitableResult returned an awaitable"):
        subscription._claim(Context())


def test_claim_condition_returns_awaitable_closes_the_coroutine() -> None:
    coroutine = async_condition()

    def condition() -> Any:
        return coroutine

    subscription = subscribe(condition=condition)
    with pytest.raises(TypeError, match=r"returned an awaitable"):
        subscription._claim(Context())
    assert inspect.getcoroutinestate(coroutine) == inspect.CORO_CLOSED


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
