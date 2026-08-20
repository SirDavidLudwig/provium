"""Shared fixtures for CLI integration tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from support.entry_point_distributions import install_entry_point_distribution

from provium import reset_procedure_discovery


@pytest.fixture(scope="session")
def pipeline_distribution(tmp_path_factory: pytest.TempPathFactory) -> Path:
    target = tmp_path_factory.mktemp("cli-plugin") / "installed"
    install_entry_point_distribution(target, "cli-pipeline", kind="shared")
    return target


@pytest.fixture
def discovered_pipeline(
    pipeline_distribution: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Path]:
    monkeypatch.syspath_prepend(pipeline_distribution)
    reset_procedure_discovery()
    yield pipeline_distribution
    reset_procedure_discovery()
