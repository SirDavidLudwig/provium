from __future__ import annotations

import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "arguments",
    [
        ("check", "src", "test"),
        ("format", "--check", "src", "test"),
    ],
    ids=("lint", "format"),
)
def test_ruff_quality_gate(arguments: tuple[str, ...]) -> None:
    subprocess.run([sys.executable, "-m", "ruff", *arguments], check=True)
