from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from dev.generate_versions import fetch_package_versions

SCRIPT = Path(__file__).parents[2] / "dev" / "generate_versions.py"


def test_fetch_package_versions_without_dependency(tmp_path: Path) -> None:
    """Test that the real functions of ``feu`` give no version for a
    ``pyproject.toml`` without dependency, which makes no request."""
    tmp_path.joinpath("pyproject.toml").write_text(
        '[project]\nname = "sample"\ndependencies = []\n'
    )
    assert fetch_package_versions(tmp_path) == {}


def test_script_without_dependency(tmp_path: Path) -> None:
    """Test that the script, run on a copy of the layout of the
    repository without dependency, writes an empty file of versions."""
    tmp_path.joinpath("pyproject.toml").write_text(
        '[project]\nname = "sample"\ndependencies = []\n'
    )
    tmp_path.joinpath("dev").mkdir()
    script = shutil.copy(SCRIPT, tmp_path / "dev")
    subprocess.run([sys.executable, "-I", script], capture_output=True, check=True)  # noqa: S603
    assert tmp_path.joinpath("dev", "config", "package_versions.json").read_text() == "{}\n"
