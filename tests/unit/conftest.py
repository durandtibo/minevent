from __future__ import annotations

import pytest

from tests.unit.utils import reset_traced


@pytest.fixture(autouse=True)
def _reset_traced() -> None:
    r"""Forget the calls recorded by the traced handlers, so a test does
    not see the calls of another test."""
    reset_traced()
