from __future__ import annotations

from typing import Any

import pytest

from minevent import PeriodicCondition

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
