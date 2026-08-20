from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def run(*arguments: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=cwd,
        env={**os.environ, "PYTHONNOUSERSITE": "1"},
        check=True,
        capture_output=True,
        text=True,
    )


def test_installed_wheels_discover_and_execute_external_plugin(
    tmp_path: Path,
) -> None:
    repository = Path(__file__).parents[4]
    distributions = tmp_path / "dist"
    distributions.mkdir()
    projects = (
        repository / "packages" / "provium",
        repository / "packages" / "provium-cli",
        Path(__file__).parent / "example_plugin",
    )
    for project in projects:
        run(
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--outdir",
            str(distributions),
            str(project),
        )

    environment = tmp_path / "environment"
    run(sys.executable, "-m", "venv", "--system-site-packages", str(environment))
    python = environment / "bin" / "python"
    wheels = tuple(str(path) for path in sorted(distributions.glob("*.whl")))
    run(str(python), "-m", "pip", "install", "--no-deps", *wheels)

    listed = run(str(python), "-m", "provium", "procedure", "list", cwd=tmp_path)
    assert "smoke.EmptyV1\tEmpty smoke procedure" in listed.stdout
    shown = run(
        str(python),
        "-m",
        "provium",
        "procedure",
        "show",
        "smoke.EmptyV1",
        cwd=tmp_path,
    )
    assert "provium execute smoke.EmptyV1" in shown.stdout
    executed = run(
        str(python),
        "-m",
        "provium",
        "execute",
        "smoke.EmptyV1",
        cwd=tmp_path,
    )
    assert executed.stdout.strip()
    console = run(
        str(environment / "bin" / "provium"),
        "procedure",
        "list",
        cwd=tmp_path,
    )
    assert console.stdout == listed.stdout
