from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from unittest.mock import patch

import pytest

import minevent


def test_version_matches_installed_package() -> None:
    assert minevent.__version__ == version("minevent")


def test_version_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(vars(minevent), "__version__", raising=False)
    assert minevent.__version__ == vars(minevent)["__version__"]


def test_version_fallback_when_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(vars(minevent), "__version__", raising=False)
    with patch("importlib.metadata.version", side_effect=PackageNotFoundError("minevent")):
        assert minevent.__version__ == "0.0.0"


def test_getattr_unknown_attribute() -> None:
    with pytest.raises(AttributeError, match=r"module 'minevent' has no attribute 'missing'"):
        minevent.missing  # noqa: B018


def test_dir_contains_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(vars(minevent), "__version__", raising=False)
    assert "__version__" in dir(minevent)
