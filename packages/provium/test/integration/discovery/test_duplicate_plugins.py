"""Integration tests for invalid and conflicting entry-point plugins."""

from pathlib import Path

import pytest
from support.entry_point_distributions import install_entry_point_distribution

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


def test_duplicate_identifiers_from_real_plugins_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "installed"
    install_entry_point_distribution(target, "duplicate-one", kind="shared")
    install_entry_point_distribution(target, "duplicate-two", kind="shared")
    monkeypatch.syspath_prepend(target)

    with pytest.raises(ValueError, match="artifact identifier is already registered"):
        discover_artifact_catalogs()
    with pytest.raises(ValueError, match="procedure identifier is already registered"):
        discover_procedure_catalogs()


@pytest.mark.parametrize(
    ("discover", "message"),
    [
        (discover_artifact_catalogs, "catalog entry point 'invalid-artifact'"),
        (
            discover_procedure_catalogs,
            "procedure catalog entry point 'invalid-procedure'",
        ),
    ],
)
def test_invalid_real_entry_point_names_appear_in_diagnostics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    discover,
    message: str,
) -> None:
    target = tmp_path / "installed"
    install_entry_point_distribution(target, "invalid", kind="invalid")
    monkeypatch.syspath_prepend(target)

    with pytest.raises(TypeError, match=message):
        discover()
