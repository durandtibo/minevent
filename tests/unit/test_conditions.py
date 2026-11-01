from __future__ import annotations

from typing import Any

import pytest

from minevent import (
    AfterNCondition,
    AlwaysCondition,
    AndCondition,
    CallableCondition,
    NotCondition,
    OnceCondition,
    OrCondition,
    PeriodicCondition,
    as_condition,
)

#######################################
#     Tests for PeriodicCondition     #
#######################################


def test_periodic_condition_str() -> None:
    assert str(PeriodicCondition(3)).startswith("PeriodicCondition(freq=3,")


@pytest.mark.parametrize("freq", [1, 2, 3])
def test_periodic_condition_freq(freq: int) -> None:
    assert PeriodicCondition(freq).freq == freq


def test_periodic_condition__eq__true() -> None:
    assert PeriodicCondition(3) == PeriodicCondition(3)


def test_periodic_condition__eq__false() -> None:
    assert PeriodicCondition(3) != PeriodicCondition(2)


def test_periodic_condition_equal_true() -> None:
    assert PeriodicCondition(3).equal(PeriodicCondition(3))


def test_periodic_condition_equal_false_different_freq() -> None:
    assert not PeriodicCondition(3).equal(PeriodicCondition(2))


def test_periodic_condition_equal_false_different_classes() -> None:
    assert not PeriodicCondition(3).equal("meow")


def test_periodic_condition_evaluate_freq_1() -> None:
    condition = PeriodicCondition(1)
    assert [condition.evaluate() for _ in range(10)] == [
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
    ]


def test_periodic_condition_evaluate_freq_2() -> None:
    condition = PeriodicCondition(2)
    assert [condition.evaluate() for _ in range(10)] == [
        True,
        False,
        True,
        False,
        True,
        False,
        True,
        False,
        True,
        False,
    ]


def test_periodic_condition_evaluate_freq_3() -> None:
    condition = PeriodicCondition(3)
    assert [condition.evaluate() for _ in range(10)] == [
        True,
        False,
        False,
        True,
        False,
        False,
        True,
        False,
        False,
        True,
    ]


##############################################################
#     Tests for PeriodicCondition validation and options     #
##############################################################


@pytest.mark.parametrize("freq", [0, -1, -3])
def test_periodic_condition_incorrect_freq_value(freq: int) -> None:
    with pytest.raises(ValueError, match=r"freq must be greater than or equal to 1"):
        PeriodicCondition(freq)


@pytest.mark.parametrize("freq", [2.9, "3", None, True])
def test_periodic_condition_incorrect_freq_type(freq: Any) -> None:
    with pytest.raises(TypeError, match=r"freq must be an integer"):
        PeriodicCondition(freq)


def test_periodic_condition_skip_first_default() -> None:
    assert not PeriodicCondition(3).skip_first


def test_periodic_condition_skip_first_true() -> None:
    assert PeriodicCondition(3, skip_first=True).skip_first


def test_periodic_condition_evaluate_sequence() -> None:
    condition = PeriodicCondition(3)
    assert [condition.evaluate() for _ in range(7)] == [
        True,
        False,
        False,
        True,
        False,
        False,
        True,
    ]


def test_periodic_condition_evaluate_skip_first_sequence() -> None:
    condition = PeriodicCondition(3, skip_first=True)
    assert [condition.evaluate() for _ in range(7)] == [
        False,
        False,
        False,
        True,
        False,
        False,
        True,
    ]


def test_periodic_condition_evaluate_freq_1_skip_first() -> None:
    condition = PeriodicCondition(1, skip_first=True)
    assert [condition.evaluate() for _ in range(3)] == [False, True, True]


def test_periodic_condition_reset() -> None:
    condition = PeriodicCondition(3)
    condition.evaluate()
    condition.evaluate()
    condition.reset()
    assert condition.evaluate()


def test_periodic_condition_reset_skip_first() -> None:
    condition = PeriodicCondition(3, skip_first=True)
    condition.evaluate()
    condition.reset()
    assert not condition.evaluate()


def test_periodic_condition_equal_ignores_step() -> None:
    condition = PeriodicCondition(3)
    condition.evaluate()
    assert condition.equal(PeriodicCondition(3))


def test_periodic_condition_equal_false_different_skip_first() -> None:
    assert not PeriodicCondition(3).equal(PeriodicCondition(3, skip_first=True))


def test_periodic_condition_repr() -> None:
    assert repr(PeriodicCondition(3, skip_first=True)) == (
        "PeriodicCondition(freq=3, skip_first=True, step=0)"
    )


def always_true() -> bool:
    return True


def always_false() -> bool:
    return False


#######################################
#     Tests for CallableCondition     #
#######################################


def test_callable_condition_repr() -> None:
    assert repr(CallableCondition(always_true)).startswith(
        "CallableCondition(func=<function always_true at"
    )


def test_callable_condition_func() -> None:
    assert CallableCondition(always_true).func is always_true


def test_callable_condition_evaluate_true() -> None:
    assert CallableCondition(always_true).evaluate()


def test_callable_condition_evaluate_false() -> None:
    assert not CallableCondition(always_false).evaluate()


def test_callable_condition_evaluate_converts_to_bool() -> None:
    assert CallableCondition(lambda: 1).evaluate() is True


def test_callable_condition_evaluate_called_each_time() -> None:
    calls = []
    condition = CallableCondition(lambda: calls.append(1) or True)
    condition.evaluate()
    condition.evaluate()
    assert len(calls) == 2


def test_callable_condition_not_callable() -> None:
    bad: Any = "meow"
    with pytest.raises(TypeError, match=r"func is not callable"):
        CallableCondition(bad)


def test_callable_condition_equal_true() -> None:
    assert CallableCondition(always_true).equal(CallableCondition(always_true))


def test_callable_condition_equal_false_different_func() -> None:
    assert not CallableCondition(always_true).equal(CallableCondition(always_false))


def test_callable_condition_equal_false_different_class() -> None:
    assert not CallableCondition(always_true).equal(AlwaysCondition())


##################################
#     Tests for as_condition     #
##################################


def test_as_condition_condition() -> None:
    condition = PeriodicCondition(2)
    assert as_condition(condition) is condition


def test_as_condition_callable() -> None:
    assert as_condition(always_true) == CallableCondition(always_true)


@pytest.mark.parametrize("condition", ["meow", None, 1])
def test_as_condition_incorrect_type(condition: Any) -> None:
    with pytest.raises(TypeError, match=r"condition must be a BaseCondition or a callable"):
        as_condition(condition)


#####################################
#     Tests for AlwaysCondition     #
#####################################


def test_always_condition_repr() -> None:
    assert repr(AlwaysCondition()) == "AlwaysCondition()"


def test_always_condition_evaluate() -> None:
    condition = AlwaysCondition()
    assert [condition.evaluate() for _ in range(3)] == [True, True, True]


def test_always_condition_equal_true() -> None:
    assert AlwaysCondition().equal(AlwaysCondition())


def test_always_condition_equal_false() -> None:
    assert not AlwaysCondition().equal(OnceCondition())


###################################
#     Tests for OnceCondition     #
###################################


def test_once_condition_repr() -> None:
    assert repr(OnceCondition()) == "OnceCondition(done=False)"


def test_once_condition_repr_after_evaluate() -> None:
    condition = OnceCondition()
    condition.evaluate()
    assert repr(condition) == "OnceCondition(done=True)"


def test_once_condition_evaluate() -> None:
    condition = OnceCondition()
    assert [condition.evaluate() for _ in range(3)] == [True, False, False]


def test_once_condition_equal_true() -> None:
    assert OnceCondition().equal(OnceCondition())


def test_once_condition_equal_true_ignores_progress() -> None:
    condition = OnceCondition()
    condition.evaluate()
    assert condition.equal(OnceCondition())


def test_once_condition_equal_false() -> None:
    assert not OnceCondition().equal(AlwaysCondition())


#####################################
#     Tests for AfterNCondition     #
#####################################


def test_after_n_condition_repr() -> None:
    assert repr(AfterNCondition(2)) == "AfterNCondition(n=2, step=0)"


def test_after_n_condition_n() -> None:
    assert AfterNCondition(2).n == 2


def test_after_n_condition_evaluate() -> None:
    condition = AfterNCondition(2)
    assert [condition.evaluate() for _ in range(4)] == [False, False, True, True]


def test_after_n_condition_evaluate_n_0() -> None:
    condition = AfterNCondition(0)
    assert [condition.evaluate() for _ in range(2)] == [True, True]


def test_after_n_condition_negative() -> None:
    with pytest.raises(ValueError, match=r"n must be greater than or equal to 0"):
        AfterNCondition(-1)


@pytest.mark.parametrize("n", [1.5, "2", None, True])
def test_after_n_condition_incorrect_type(n: Any) -> None:
    with pytest.raises(TypeError, match=r"n must be an integer"):
        AfterNCondition(n)


def test_after_n_condition_equal_true() -> None:
    assert AfterNCondition(2).equal(AfterNCondition(2))


def test_after_n_condition_equal_false_different_n() -> None:
    assert not AfterNCondition(2).equal(AfterNCondition(3))


def test_after_n_condition_equal_false_different_class() -> None:
    assert not AfterNCondition(2).equal(PeriodicCondition(2))


##################################
#     Tests for AndCondition     #
##################################


def test_and_condition_repr() -> None:
    assert repr(AndCondition(AlwaysCondition(), OnceCondition())) == (
        "AndCondition(AlwaysCondition(), OnceCondition(done=False))"
    )


def test_and_condition_conditions() -> None:
    assert AndCondition(AlwaysCondition(), always_true).conditions == (
        AlwaysCondition(),
        CallableCondition(always_true),
    )


def test_and_condition_evaluate() -> None:
    condition = AndCondition(AfterNCondition(1), PeriodicCondition(2))
    assert [condition.evaluate() for _ in range(5)] == [False, False, True, False, True]


def test_and_condition_evaluate_all_conditions_advance() -> None:
    once = OnceCondition()
    condition = AndCondition(always_false, once)
    condition.evaluate()
    assert not once.evaluate()


def test_and_condition_no_condition() -> None:
    with pytest.raises(ValueError, match=r"AndCondition requires at least one condition"):
        AndCondition()


def test_and_condition_incorrect_condition() -> None:
    bad: Any = "meow"
    with pytest.raises(TypeError, match=r"condition must be a BaseCondition or a callable"):
        AndCondition(bad)


def test_and_condition_equal_true() -> None:
    assert AndCondition(AlwaysCondition(), always_true).equal(
        AndCondition(AlwaysCondition(), always_true)
    )


def test_and_condition_equal_false_different_conditions() -> None:
    assert not AndCondition(AlwaysCondition()).equal(AndCondition(OnceCondition()))


def test_and_condition_equal_false_different_class() -> None:
    assert not AndCondition(AlwaysCondition()).equal(OrCondition(AlwaysCondition()))


#################################
#     Tests for OrCondition     #
#################################


def test_or_condition_evaluate() -> None:
    condition = OrCondition(OnceCondition(), PeriodicCondition(3))
    assert [condition.evaluate() for _ in range(4)] == [True, False, False, True]


def test_or_condition_evaluate_all_false() -> None:
    assert not OrCondition(always_false, always_false).evaluate()


def test_or_condition_evaluate_all_conditions_advance() -> None:
    once = OnceCondition()
    condition = OrCondition(always_true, once)
    condition.evaluate()
    assert not once.evaluate()


def test_or_condition_no_condition() -> None:
    with pytest.raises(ValueError, match=r"OrCondition requires at least one condition"):
        OrCondition()


def test_or_condition_equal_true() -> None:
    assert OrCondition(AlwaysCondition()).equal(OrCondition(AlwaysCondition()))


##################################
#     Tests for NotCondition     #
##################################


def test_not_condition_repr() -> None:
    assert repr(NotCondition(AlwaysCondition())) == "NotCondition(AlwaysCondition())"


def test_not_condition_condition() -> None:
    assert NotCondition(always_true).condition == CallableCondition(always_true)


def test_not_condition_evaluate() -> None:
    condition = NotCondition(OnceCondition())
    assert [condition.evaluate() for _ in range(3)] == [False, True, True]


def test_not_condition_incorrect_condition() -> None:
    bad: Any = "meow"
    with pytest.raises(TypeError, match=r"condition must be a BaseCondition or a callable"):
        NotCondition(bad)


def test_not_condition_equal_true() -> None:
    assert NotCondition(AlwaysCondition()).equal(NotCondition(AlwaysCondition()))


def test_not_condition_equal_false_different_condition() -> None:
    assert not NotCondition(AlwaysCondition()).equal(NotCondition(OnceCondition()))


def test_not_condition_equal_false_different_class() -> None:
    assert not NotCondition(AlwaysCondition()).equal(AlwaysCondition())


def test_periodic_condition_unhashable() -> None:
    with pytest.raises(TypeError, match=r"unhashable type: 'PeriodicCondition'"):
        hash(PeriodicCondition(3))
