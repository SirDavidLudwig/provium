"""Build and install tiny distributions for real entry-point integration tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from textwrap import dedent
from typing import Literal


def install_entry_point_distribution(
    target: Path,
    name: str,
    *,
    kind: Literal["shared", "additional", "invalid"],
) -> None:
    """Install one deterministic fixture distribution into ``target``."""
    source = target.parent / f"source-{name}"
    package_name = f"provium_fixture_{name.replace('-', '_')}"
    package = source / "src" / package_name
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        '"""Temporary Provium entry-point fixture."""\n',
        encoding="utf-8",
    )
    module, artifact_value, procedure_value = _entry_point_values(
        kind,
        package_name,
    )
    if module is not None:
        (package / "catalogs.py").write_text(module, encoding="utf-8")
    (source / "pyproject.toml").write_text(
        dedent(
            f"""
            [build-system]
            requires = ["setuptools>=77"]
            build-backend = "setuptools.build_meta"

            [project]
            name = "provium-fixture-{name}"
            version = "1.0.0"
            requires-python = ">=3.12"

            [project.entry-points."provium.catalogs"]
            "{artifact_value[0]}" = "{artifact_value[1]}"

            [project.entry-points."provium.procedure_catalogs"]
            "{procedure_value[0]}" = "{procedure_value[1]}"

            [tool.setuptools.packages.find]
            where = ["src"]
            """
        ).lstrip(),
        encoding="utf-8",
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-deps",
            "--target",
            str(target),
            str(source),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def _entry_point_values(
    kind: str,
    package_name: str,
) -> tuple[str | None, tuple[str, str], tuple[str, str]]:
    if kind == "shared":
        return (
            None,
            (
                f"artifact-{package_name}",
                "support.provium_test_pipeline.catalogs:artifact_catalog",
            ),
            (
                f"procedure-{package_name}",
                "support.provium_test_pipeline.catalogs:procedure_catalog",
            ),
        )
    if kind == "invalid":
        target = f"{package_name}.catalogs:not_a_catalog"
        return (
            "not_a_catalog = object()\n",
            ("invalid-artifact", target),
            ("invalid-procedure", target),
        )
    module = dedent(
        """
        from provium import (
            ArtifactCatalog,
            ArtifactDefinition,
            ProcedureCatalog,
            ProcedureContract,
            ProcedureDefinition,
        )

        artifact_catalog = ArtifactCatalog()
        artifact_catalog.register(
            ArtifactDefinition(
                "fixture.AdditionalTextV1",
                "support.provium_test_pipeline.artifacts:TextArtifact",
                "An additional discovery-only artifact.",
            )
        )

        class AdditionalContract(ProcedureContract[None]):
            configuration = None

        procedure_catalog = ProcedureCatalog()
        procedure_catalog.register(
            ProcedureDefinition(
                "fixture.AdditionalProcedureV1",
                "support.provium_test_pipeline.procedures:SourceProcedure",
                "Additional procedure",
                "A discovery-only procedure.",
                AdditionalContract,
            )
        )
        """
    ).lstrip()
    return (
        module,
        ("additional-artifact", f"{package_name}.catalogs:artifact_catalog"),
        ("additional-procedure", f"{package_name}.catalogs:procedure_catalog"),
    )
