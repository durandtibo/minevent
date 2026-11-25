from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PACKAGE_CHECKS = Path(__file__).parents[1] / "package_checks.py"


def test_package_checks_pass() -> None:
    """Test that the checks of the built package pass on the source."""
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-I", str(PACKAGE_CHECKS)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
