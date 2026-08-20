"""Integration tests for lazy implementation imports through entry points."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from support.entry_point_distributions import install_entry_point_distribution


def test_discovery_and_quick_metadata_do_not_import_implementations(
    tmp_path: Path,
) -> None:
    target = tmp_path / "installed"
    install_entry_point_distribution(target, "lazy", kind="shared")
    package_root = Path(__file__).parents[3]
    pythonpath = os.pathsep.join(
        (
            str(target),
            str(package_root / "src"),
            str(package_root / "test"),
        )
    )
    common_script = """
from pathlib import Path
from provium import discover_artifact_catalogs, discover_procedure_catalogs

sentinel = Path(sentinel_path)
artifacts = discover_artifact_catalogs()
procedures = discover_procedure_catalogs()
artifact = artifacts.resolve("test.TextV1")
procedure = procedures.resolve("test.TransformTextV1")
assert artifact.description
assert procedure.contract.metadata.inputs
assert procedure.invocation_synopsis
assert not sentinel.exists()
"""

    scenarios = (
        (
            tmp_path / "artifact-imports.log",
            "artifact.resolve()",
            ["artifacts"],
        ),
        (
            tmp_path / "procedure-imports.log",
            "procedure.resolve()",
            ["procedures", "artifacts"],
        ),
    )
    for sentinel, resolution, expected_imports in scenarios:
        environment = os.environ.copy()
        environment["PROVIUM_TEST_IMPORT_SENTINEL"] = str(sentinel)
        environment["PYTHONPATH"] = pythonpath
        script = (
            f"sentinel_path = {str(sentinel)!r}\n"
            f"{common_script}\n"
            f"{resolution}\n"
            f"assert sentinel.read_text().splitlines() == {expected_imports!r}\n"
        )

        subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            cwd=package_root,
            env=environment,
        )
