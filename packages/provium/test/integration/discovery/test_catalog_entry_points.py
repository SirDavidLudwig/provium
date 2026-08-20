"""Integration tests for catalogs installed through package entry points."""

from pathlib import Path

import pytest
from support.entry_point_distributions import install_entry_point_distribution
from support.provium_test_pipeline.catalogs import (
    artifact_catalog,
    procedure_catalog,
)

from provium import (
    discover_artifact_catalogs,
    discover_procedure_catalogs,
    reset_artifact_discovery,
    reset_procedure_discovery,
)


@pytest.fixture(autouse=True)
def reset_discovery() -> None:
    reset_artifact_discovery()
    reset_procedure_discovery()
    yield
    reset_artifact_discovery()
    reset_procedure_discovery()


def test_real_entry_point_catalogs_are_merged_and_cached(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline_artifacts = set(discover_artifact_catalogs().definitions)
    baseline_procedures = set(discover_procedure_catalogs().definitions)
    reset_artifact_discovery()
    reset_procedure_discovery()
    target = tmp_path / "installed"
    install_entry_point_distribution(target, "primary", kind="shared")
    install_entry_point_distribution(target, "additional", kind="additional")
    monkeypatch.syspath_prepend(target)

    artifacts = discover_artifact_catalogs()
    procedures = discover_procedure_catalogs()

    assert set(artifacts.definitions) == baseline_artifacts | set(
        artifact_catalog.definitions
    ) | {"fixture.AdditionalTextV1"}
    assert set(procedures.definitions) == baseline_procedures | set(
        procedure_catalog.definitions
    ) | {"fixture.AdditionalProcedureV1"}
    assert discover_artifact_catalogs() is artifacts
    assert discover_procedure_catalogs() is procedures

    reset_artifact_discovery()
    reset_procedure_discovery()
    assert discover_artifact_catalogs() is not artifacts
    assert discover_procedure_catalogs() is not procedures
