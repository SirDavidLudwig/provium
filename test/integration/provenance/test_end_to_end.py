from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pytest

from provium import (
    Artifact,
    ArtifactCatalog,
    ArtifactDefinition,
    ArtifactLineage,
    ArtifactReader,
    ArtifactReference,
    ArtifactWriter,
    JsonValue,
    Procedure,
)


class BytesReader(ArtifactReader):
    def read(self) -> bytes:
        return self.body.read()


class BytesWriter(ArtifactWriter):
    def write(self, value: bytes) -> int:
        return self.body.write(value)


BytesArtifact = Artifact("example.BytesV1", "Bytes", BytesReader, BytesWriter)


@dataclass(frozen=True)
class LabelConfig:
    label: str


class LabelCodec:
    identifier = "label-v1"

    def encode(self, config: LabelConfig) -> JsonValue:
        return {"label": config.label}

    def decode(self, value: object) -> LabelConfig:
        if not isinstance(value, dict):
            raise TypeError("expected object")
        return LabelConfig(str(value["label"]))


@pytest.fixture(autouse=True)
def discovered_catalog(monkeypatch: pytest.MonkeyPatch) -> ArtifactCatalog:
    catalog = ArtifactCatalog()
    catalog.register(
        ArtifactDefinition("example.BytesV1", f"{__name__}:BytesArtifact", "Bytes.")
    )
    monkeypatch.setattr("provium.procedure.discover_catalogs", lambda: catalog)
    return catalog


@dataclass(frozen=True)
class Graph:
    root: ArtifactReference
    left: ArtifactReference
    right: ArtifactReference
    final: ArtifactReference
    root_execution: str
    left_execution: str
    right_execution: str
    final_execution: str


def build_graph(tmp_path: Path) -> tuple[Path, Graph]:
    root_path = tmp_path / "root.pa"
    with Procedure[LabelConfig]("root", "1", LabelCodec()).execute(
        config=LabelConfig("seed")
    ) as root_execution:
        root_writer = BytesArtifact.create(root_path)
        root_writer.write(b"root")

    left_path = tmp_path / "left.pa"
    with Procedure[LabelConfig]("branch-left", "2", LabelCodec()).execute(
        config=LabelConfig("left")
    ) as left_execution:
        root_reader = BytesArtifact.open(root_path)
        left_writer = BytesArtifact.create(left_path)
        left_writer.write(root_reader.read() + b"-left")

    right_path = tmp_path / "right.pa"
    with Procedure[LabelConfig]("branch-right", "3", LabelCodec()).execute(
        config=LabelConfig("right")
    ) as right_execution:
        root_reader = BytesArtifact.open(root_path)
        right_writer = BytesArtifact.create(right_path)
        right_writer.write(root_reader.read() + b"-right")

    final_path = tmp_path / "final.pa"
    with Procedure[LabelConfig]("join", "4", LabelCodec()).execute(
        config=LabelConfig("final")
    ) as final_execution:
        left_reader = BytesArtifact.open(left_path)
        right_reader = BytesArtifact.open(right_path)
        final_writer = BytesArtifact.create(final_path)
        final_writer.write(left_reader.read() + b"+" + right_reader.read())

    return final_path, Graph(
        root=ArtifactReference(root_writer.identity, "example.BytesV1"),
        left=ArtifactReference(left_writer.identity, "example.BytesV1"),
        right=ArtifactReference(right_writer.identity, "example.BytesV1"),
        final=ArtifactReference(final_writer.identity, "example.BytesV1"),
        root_execution=root_execution.identity,
        left_execution=left_execution.identity,
        right_execution=right_execution.identity,
        final_execution=final_execution.identity,
    )


def test_reconstructs_complete_branching_provenance_from_final_artifact(
    tmp_path: Path,
) -> None:
    final_path, graph = build_graph(tmp_path)

    with Procedure("inspect", "1").execute():
        final_reader = BytesArtifact.open(final_path)
        lineage = final_reader.lineage
        assert final_reader.read() == b"root-left+root-right"

    assert set(lineage.artifacts) == {
        graph.root.identity,
        graph.left.identity,
        graph.right.identity,
        graph.final.identity,
    }
    assert set(lineage.executions) == {
        graph.root_execution,
        graph.left_execution,
        graph.right_execution,
        graph.final_execution,
    }
    assert len(lineage.artifacts) == 4
    assert len(lineage.executions) == 4
    assert lineage.ancestry(graph.final) == lineage


def test_preserves_procedure_records_configuration_and_graph_edges(
    tmp_path: Path,
) -> None:
    final_path, graph = build_graph(tmp_path)

    with Procedure("inspect", "1").execute():
        lineage = BytesArtifact.open(final_path).lineage

    expected_procedures = {
        graph.root_execution: ("root", "1", {"label": "seed"}),
        graph.left_execution: ("branch-left", "2", {"label": "left"}),
        graph.right_execution: ("branch-right", "3", {"label": "right"}),
        graph.final_execution: ("join", "4", {"label": "final"}),
    }
    for identity, (name, version, config) in expected_procedures.items():
        procedure = lineage.executions[identity].procedure
        assert (procedure.name, procedure.version, procedure.config) == (
            name,
            version,
            config,
        )
        assert procedure.config_codec == "label-v1"

    assert lineage.executions[graph.root_execution].inputs == ()
    assert lineage.executions[graph.root_execution].outputs == (graph.root,)
    assert lineage.executions[graph.left_execution].inputs == (graph.root,)
    assert lineage.executions[graph.left_execution].outputs == (graph.left,)
    assert lineage.executions[graph.right_execution].inputs == (graph.root,)
    assert lineage.executions[graph.right_execution].outputs == (graph.right,)
    assert set(lineage.executions[graph.final_execution].inputs) == {
        graph.left,
        graph.right,
    }
    assert lineage.executions[graph.final_execution].outputs == (graph.final,)


def test_preserves_artifact_identities_identifiers_digests_and_producers(
    tmp_path: Path,
) -> None:
    final_path, graph = build_graph(tmp_path)

    with Procedure("inspect", "1").execute():
        lineage = BytesArtifact.open(final_path).lineage

    expected = {
        graph.root: (b"root", graph.root_execution),
        graph.left: (b"root-left", graph.left_execution),
        graph.right: (b"root-right", graph.right_execution),
        graph.final: (b"root-left+root-right", graph.final_execution),
    }
    for reference, (body, execution_identity) in expected.items():
        record = lineage.artifact(reference)
        assert record.reference.artifact_identifier == "example.BytesV1"
        assert record.body_digest == hashlib.sha256(body).hexdigest()
        assert record.producer_execution_identity == execution_identity
        assert lineage.producing_execution(reference).identity == execution_identity


def test_complete_lineage_round_trips_after_disk_serialization(tmp_path: Path) -> None:
    final_path, graph = build_graph(tmp_path)

    with Procedure("inspect", "1").execute():
        lineage = BytesArtifact.open(final_path).lineage

    encoded = lineage.to_json()
    restored = ArtifactLineage.from_json(encoded)

    assert restored == lineage
    assert restored.ancestry(graph.final) == restored
    assert restored.to_json() == encoded
