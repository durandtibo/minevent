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


def test_periodic_condition_start_default() -> None:
    assert PeriodicCondition(3).start == 0


@pytest.mark.parametrize("start", [0, 1, 3, 100])
def test_periodic_condition_start(start: int) -> None:
    assert PeriodicCondition(3, start=start).start == start


@pytest.mark.parametrize("start", [-1, -3])
def test_periodic_condition_incorrect_start_value(start: int) -> None:
    with pytest.raises(ValueError, match=r"start must be greater than or equal to 0, got -"):
        PeriodicCondition(3, start=start)


@pytest.mark.parametrize("start", [2.9, "3", None, True, False])
def test_periodic_condition_incorrect_start_type(start: Any) -> None:
    with pytest.raises(TypeError, match=r"start must be an integer, got "):
        PeriodicCondition(3, start=start)


def test_periodic_condition_start_is_keyword_only() -> None:
    args: list[Any] = [3, 1]
    with pytest.raises(TypeError, match=r"positional argument"):
        PeriodicCondition(*args)


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


@pytest.mark.parametrize(
    ("freq", "start", "expected"),
    [
        (3, 0, "TFFTFFTFFT"),
        (3, 2, "FFTFFTFFTF"),
        (3, 3, "FFFTFFTFFT"),
        (3, 5, "FFFFFTFFTF"),
        (2, 7, "FFFFFFFTFT"),
        (1, 0, "TTTTTTTTTT"),
        (1, 1, "FTTTTTTTTT"),
        (4, 20, "FFFFFFFFFF"),
    ],
)
def test_periodic_condition_call_start(freq: int, start: int, expected: str) -> None:
    condition = PeriodicCondition(freq, start=start)
    assert "".join("T" if condition() else "F" for _ in range(10)) == expected


def test_periodic_condition_reset() -> None:
    condition = PeriodicCondition(3)
    condition()
    condition()
    condition.reset()
    assert condition()


def test_periodic_condition_reset_start() -> None:
    condition = PeriodicCondition(3, start=1)
    condition()
    condition()
    condition.reset()
    assert [condition() for _ in range(2)] == [False, True]


def test_periodic_condition_repr() -> None:
    assert repr(PeriodicCondition(3, start=2)) == "PeriodicCondition(freq=3, start=2, step=0)"


def test_periodic_condition_repr_large_values() -> None:
    assert repr(PeriodicCondition(1000, start=2000)) == (
        "PeriodicCondition(freq=1,000, start=2,000, step=0)"
    )


def always_true() -> bool:
    r"""Implement a condition that is ``True``."""
    return True


def always_false() -> bool:
    r"""Implement a condition that is ``False``."""
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
    condition = PeriodicCondition(3, start=2)
    condition()
    assert condition.__getstate__() == {"_step": 1, "_freq": 3, "_start": 2}


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
        (PeriodicCondition, "PeriodicCondition(freq=3, start=0, step=1)"),
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
