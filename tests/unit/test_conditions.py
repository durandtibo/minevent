from __future__ import annotations

from typing import Any

import pytest

from minevent import AfterNCondition, PeriodicCondition

#######################################
#     Tests for PeriodicCondition     #
#######################################


def test_periodic_condition_str() -> None:
    assert str(PeriodicCondition(3)).startswith("PeriodicCondition(freq=3,")


@pytest.mark.parametrize("freq", [1, 2, 3])
def test_periodic_condition_freq(freq: int) -> None:
    assert PeriodicCondition(freq).freq == freq


@pytest.mark.parametrize(
    ("freq", "expected"),
    [
        (1, "TTTTTTTTTT"),
        (2, "TFTFTFTFTF"),
        (3, "TFFTFFTFFT"),
        (4, "TFFFTFFFTF"),
    ],
)
def test_periodic_condition_call_freq(freq: int, expected: str) -> None:
    condition = PeriodicCondition(freq)
    assert "".join("T" if condition() else "F" for _ in range(10)) == expected


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


def test_periodic_condition_call_sequence() -> None:
    condition = PeriodicCondition(3)
    assert [condition() for _ in range(7)] == [
        True,
        False,
        False,
        True,
        False,
        False,
        True,
    ]


def test_periodic_condition_call_skip_first_sequence() -> None:
    condition = PeriodicCondition(3, skip_first=True)
    assert [condition() for _ in range(7)] == [
        False,
        False,
        False,
        True,
        False,
        False,
        True,
    ]


def test_periodic_condition_call_freq_1_skip_first() -> None:
    condition = PeriodicCondition(1, skip_first=True)
    assert [condition() for _ in range(3)] == [False, True, True]


def test_periodic_condition_reset() -> None:
    condition = PeriodicCondition(3)
    condition()
    condition()
    condition.reset()
    assert condition()


def test_periodic_condition_reset_skip_first() -> None:
    condition = PeriodicCondition(3, skip_first=True)
    condition()
    condition.reset()
    assert not condition()


def test_periodic_condition_repr() -> None:
    assert repr(PeriodicCondition(3, skip_first=True)) == (
        "PeriodicCondition(freq=3, skip_first=True, step=0)"
    )


def always_true() -> bool:
    return True


def always_false() -> bool:
    return False


#####################################
#     Tests for AfterNCondition     #
#####################################


def test_after_n_condition_repr() -> None:
    assert repr(AfterNCondition(2)) == "AfterNCondition(n=2, step=0)"


def test_after_n_condition_n() -> None:
    assert AfterNCondition(2).n == 2


def test_after_n_condition_call() -> None:
    condition = AfterNCondition(2)
    assert [condition() for _ in range(4)] == [False, False, True, True]


def test_after_n_condition_call_n_0() -> None:
    condition = AfterNCondition(0)
    assert [condition() for _ in range(2)] == [True, True]


def test_after_n_condition_reset() -> None:
    condition = AfterNCondition(2)
    condition()
    condition()
    condition.reset()
    assert [condition() for _ in range(3)] == [False, False, True]


def test_after_n_condition_reset_restores_initial_state() -> None:
    condition = AfterNCondition(2)
    condition()
    condition()
    condition()
    condition.reset()
    assert repr(condition) == "AfterNCondition(n=2, step=0)"


def test_after_n_condition_reset_before_first_call() -> None:
    condition = AfterNCondition(1)
    condition.reset()
    assert [condition() for _ in range(2)] == [False, True]


def test_after_n_condition_negative() -> None:
    with pytest.raises(ValueError, match=r"n must be greater than or equal to 0"):
        AfterNCondition(-1)


@pytest.mark.parametrize("n", [1.5, "2", None, True])
def test_after_n_condition_incorrect_type(n: Any) -> None:
    with pytest.raises(TypeError, match=r"n must be an integer"):
        AfterNCondition(n)
