from __future__ import annotations

from importlib.metadata import version

import minevent


def test_version_matches_installed_package() -> None:
    assert minevent.__version__ == version("minevent")


def test_version_is_not_placeholder() -> None:
    assert minevent.__version__ != "0.0.0"
