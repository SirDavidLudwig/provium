"""Acceptance tests for the shared integration pipeline fixture."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_catalogs_are_lightweight_and_definitions_resolve_lazily(
    tmp_path: Path,
) -> None:
    sentinel = tmp_path / "imports.log"
    script = """
from support.provium_test_pipeline.catalogs import (
    artifact_catalog,
    procedure_catalog,
)
from support.provium_test_pipeline.contracts import (
    FAILING_PROCEDURE,
    SOURCE_PROCEDURE,
    TEXT_ARTIFACT,
    TRANSFORM_PROCEDURE,
    TransformConfig,
)

assert tuple(artifact_catalog.definitions) == (TEXT_ARTIFACT.identifier,)
assert tuple(procedure_catalog.definitions) == (
    SOURCE_PROCEDURE.identifier,
    TRANSFORM_PROCEDURE.identifier,
    FAILING_PROCEDURE.identifier,
)
assert TransformConfig(prefix="[", suffix="]").model_dump() == {
    "prefix": "[",
    "suffix": "]",
}
metadata = TRANSFORM_PROCEDURE.contract.metadata
assert [field.name for field in metadata.setup_inputs] == ["setup"]
assert [field.name for field in metadata.inputs] == [
    "required",
    "optional",
    "repeated",
]
assert [field.name for field in metadata.outputs] == ["transformed", "summary"]
assert (metadata.inputs[1].minimum, metadata.inputs[1].maximum) == (0, 1)
assert (metadata.inputs[2].minimum, metadata.inputs[2].maximum) == (1, 4)
assert not sentinel.exists()

artifact_class = TEXT_ARTIFACT.resolve()
assert artifact_class.definition is TEXT_ARTIFACT
assert sentinel.read_text().splitlines() == ["artifacts"]

procedure_class = TRANSFORM_PROCEDURE.resolve()
assert procedure_class.definition is TRANSFORM_PROCEDURE
assert sentinel.read_text().splitlines() == ["artifacts", "procedures"]
assert SOURCE_PROCEDURE.resolve().definition is SOURCE_PROCEDURE
assert FAILING_PROCEDURE.resolve().definition is FAILING_PROCEDURE
assert sentinel.read_text().splitlines() == ["artifacts", "procedures"]
"""
    environment = os.environ.copy()
    environment["PROVIUM_TEST_IMPORT_SENTINEL"] = str(sentinel)
    package_root = Path(__file__).parents[2]
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(
            None,
            (
                str(package_root / "src"),
                str(package_root / "test"),
                environment.get("PYTHONPATH"),
            ),
        )
    )
    command = f"from pathlib import Path\nsentinel = Path({str(sentinel)!r})\n{script}"
    subprocess.run(
        [sys.executable, "-c", command],
        check=True,
        cwd=package_root,
        env=environment,
    )
