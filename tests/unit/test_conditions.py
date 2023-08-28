from __future__ import annotations

from pytest import mark

from minevent import PeriodicCondition

#######################################
#     Tests for PeriodicCondition     #
#######################################


def test_periodic_condition_str() -> None:
    assert str(PeriodicCondition(3)).startswith("PeriodicCondition(freq=3,")


@mark.parametrize("freq", (1, 2, 3))
def test_periodic_condition_freq(freq: int) -> None:
    assert PeriodicCondition(freq).freq == freq


def test_periodic_condition_eq_true() -> None:
    assert PeriodicCondition(3) == PeriodicCondition(3)


def test_periodic_condition_eq_false_different_freq() -> None:
    assert PeriodicCondition(3) != PeriodicCondition(2)


def test_periodic_condition_eq_false_different_classes() -> None:
    assert PeriodicCondition(3) != "meow"


def test_periodic_condition_freq_1() -> None:
    condition = PeriodicCondition(1)
    assert [condition() for _ in range(10)] == [
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


def test_periodic_condition_freq_2() -> None:
    condition = PeriodicCondition(2)
    assert [condition() for _ in range(10)] == [
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


def test_periodic_condition_freq_3() -> None:
    condition = PeriodicCondition(3)
    assert [condition() for _ in range(10)] == [
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
