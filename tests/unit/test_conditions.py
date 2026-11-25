from __future__ import annotations

import copy
import pickle
from typing import TYPE_CHECKING, Any

import pytest

from minevent import AfterNCondition, PeriodicCondition

if TYPE_CHECKING:
    from collections.abc import Callable

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


########################################
#     Tests for _CountingCondition     #
########################################


@pytest.mark.parametrize("condition_class", [PeriodicCondition, AfterNCondition])
def test_counting_condition_next_step_first(
    condition_class: type[PeriodicCondition | AfterNCondition],
) -> None:
    assert condition_class(3)._next_step() == 0


def test_counting_condition_next_step_increments() -> None:
    condition = AfterNCondition(3)
    assert [condition._next_step() for _ in range(3)] == [0, 1, 2]


def test_counting_condition_next_step_after_reset() -> None:
    condition = AfterNCondition(3)
    condition()
    condition.reset()
    assert condition._next_step() == 0


def test_counting_condition_next_step_releases_the_lock() -> None:
    condition = AfterNCondition(3)
    condition._next_step()
    assert not condition._lock.locked()


def test_counting_condition_reset_releases_the_lock() -> None:
    condition = AfterNCondition(3)
    condition.reset()
    assert not condition._lock.locked()


def test_counting_condition_getstate() -> None:
    condition = PeriodicCondition(3, skip_first=True)
    condition()
    assert condition.__getstate__() == {"_step": 1, "_freq": 3, "_skip_first": True}


def test_counting_condition_getstate_does_not_remove_the_lock() -> None:
    condition = AfterNCondition(3)
    condition.__getstate__()
    assert hasattr(condition, "_lock")


def test_counting_condition_setstate() -> None:
    condition = AfterNCondition(3)
    condition.__setstate__({"_step": 2, "_n": 5})
    assert repr(condition) == "AfterNCondition(n=5, step=2)"


def test_counting_condition_setstate_creates_a_new_lock() -> None:
    condition = AfterNCondition(3)
    lock = condition._lock
    condition.__setstate__({"_step": 2, "_n": 5})
    assert condition._lock is not lock


@pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
@pytest.mark.parametrize("condition_class", [PeriodicCondition, AfterNCondition])
def test_condition_pickle(
    condition_class: type[PeriodicCondition | AfterNCondition], protocol: int
) -> None:
    assert pickle.dumps(condition_class(3), protocol)


@pytest.mark.parametrize("copier", [copy.copy, copy.deepcopy])
@pytest.mark.parametrize(
    ("condition_class", "expected"),
    [
        (PeriodicCondition, "PeriodicCondition(freq=3, skip_first=False, step=1)"),
        (AfterNCondition, "AfterNCondition(n=3, step=1)"),
    ],
)
def test_condition_copy_starts_at_the_same_step(
    condition_class: type[PeriodicCondition | AfterNCondition],
    expected: str,
    copier: Callable[[Any], Any],
) -> None:
    condition = condition_class(3)
    condition()
    assert repr(copier(condition)) == expected


@pytest.mark.parametrize("copier", [copy.copy, copy.deepcopy])
def test_condition_copy_has_an_independent_counter(copier: Callable[[Any], Any]) -> None:
    condition = AfterNCondition(3)
    clone = copier(condition)
    clone()
    assert repr(condition) == "AfterNCondition(n=3, step=0)"


@pytest.mark.parametrize("copier", [copy.copy, copy.deepcopy])
def test_condition_copy_has_an_independent_lock(copier: Callable[[Any], Any]) -> None:
    condition = AfterNCondition(3)
    assert copier(condition)._lock is not condition._lock
