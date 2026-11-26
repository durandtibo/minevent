from __future__ import annotations

import importlib
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

import minevent

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def restore_minevent() -> Iterator[None]:
    r"""Execute the ``minevent`` package again after the test, so the
    version read by the test does not stay."""
    yield
    importlib.reload(minevent)


def test_version_matches_installed_package() -> None:
    assert minevent.__version__ == version("minevent")


@pytest.mark.usefixtures("restore_minevent")
def test_version_fallback_when_not_installed() -> None:
    with patch("importlib.metadata.version", side_effect=PackageNotFoundError("minevent")):
        importlib.reload(minevent)
    assert minevent.__version__ == "0.0.0"
