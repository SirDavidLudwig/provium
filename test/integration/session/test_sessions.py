from importlib import import_module
from pathlib import Path

import pytest

from provium import (
    Artifact,
    ArtifactCatalog,
    ArtifactReader,
    ArtifactWriter,
    Procedure,
    current_session,
    decode_header,
    session,
)
from provium.context import activate_context


class BytesReader(ArtifactReader):
    def read(self) -> bytes:
        return self.body.read()


class BytesWriter(ArtifactWriter):
    def write(self, value: bytes) -> None:
        self.body.write(value)


class BytesArtifact(Artifact[BytesReader, BytesWriter]):
    reader = BytesReader
    writer = BytesWriter


@pytest.fixture(autouse=True)
def discovered_catalog(monkeypatch: pytest.MonkeyPatch) -> ArtifactCatalog:
    catalog = ArtifactCatalog()
    catalog.register("example.BytesV1", BytesArtifact)

    def discover() -> ArtifactCatalog:
        return catalog

    monkeypatch.setattr("provium.procedure.discover_catalogs", discover)
    monkeypatch.setattr(import_module("provium.session"), "discover_catalogs", discover)
    return catalog


def create_bytes(path: Path, value: bytes) -> str:
    with Procedure("seed", "1").execute():
        writer = BytesArtifact.create(path)
        writer.write(value)
    return writer.identity


def test_generic_session_opens_artifact_without_a_procedure(tmp_path: Path) -> None:
    path = tmp_path / "input.pa"
    identity = create_bytes(path, b"value")

    with session() as active:
        reader = BytesArtifact.open(path)
        assert current_session() is active
        assert reader.read() == b"value"
        assert active.inputs[0].reference.identity == identity

    assert current_session() is None
    assert reader.closed


def test_closed_artifact_remains_in_session_provenance(tmp_path: Path) -> None:
    source = tmp_path / "source.pa"
    output = tmp_path / "output.pa"
    source_identity = create_bytes(source, b"materialized")

    with session() as active:
        reader = BytesArtifact.open(source)
        materialized = reader.read()
        reader.close()

        assert active.inputs[0].reference.identity == source_identity
        with Procedure("consume-materialized", "1").execute():
            writer = BytesArtifact.create(output)
            writer.write(materialized)

    execution = decode_header(output.read_bytes()).lineage.producing_execution(
        decode_header(output.read_bytes()).lineage.artifacts[writer.identity].reference
    )
    assert tuple(reference.identity for reference in execution.inputs) == (
        source_identity,
    )


def test_execution_local_inputs_do_not_leak_between_calls(tmp_path: Path) -> None:
    model_path = tmp_path / "model.pa"
    first_data_path = tmp_path / "first-data.pa"
    second_data_path = tmp_path / "second-data.pa"
    first_output = tmp_path / "first-output.pa"
    second_output = tmp_path / "second-output.pa"
    model_identity = create_bytes(model_path, b"model")
    first_data_identity = create_bytes(first_data_path, b"one")
    second_data_identity = create_bytes(second_data_path, b"two")

    with session():
        model_reader = BytesArtifact.open(model_path)
        model = model_reader.read()
        model_reader.close()

        for data_path, output_path in (
            (first_data_path, first_output),
            (second_data_path, second_output),
        ):
            with Procedure("predict", "1").execute():
                data = BytesArtifact.open(data_path).read()
                writer = BytesArtifact.create(output_path)
                writer.write(model + data)

    first_lineage = decode_header(first_output.read_bytes()).lineage
    second_lineage = decode_header(second_output.read_bytes()).lineage
    first_execution = first_lineage.producing_execution(
        first_lineage.artifacts[
            decode_header(first_output.read_bytes()).artifact_identity
        ].reference
    )
    second_execution = second_lineage.producing_execution(
        second_lineage.artifacts[
            decode_header(second_output.read_bytes()).artifact_identity
        ].reference
    )
    assert {item.identity for item in first_execution.inputs} == {
        model_identity,
        first_data_identity,
    }
    assert {item.identity for item in second_execution.inputs} == {
        model_identity,
        second_data_identity,
    }


def test_nested_generic_sessions_inherit_ancestor_dependencies(tmp_path: Path) -> None:
    parent_path = tmp_path / "parent.pa"
    child_path = tmp_path / "child.pa"
    parent_identity = create_bytes(parent_path, b"parent")
    child_identity = create_bytes(child_path, b"child")

    with session() as parent:
        BytesArtifact.open(parent_path).close()
        with session() as child:
            BytesArtifact.open(child_path).close()
            assert child.parent is parent
            assert {record.reference.identity for record in child.inputs} == {
                parent_identity,
                child_identity,
            }
        assert {record.reference.identity for record in parent.inputs} == {
            parent_identity
        }


def test_sessions_are_single_use_and_require_matching_context() -> None:
    reusable = session()
    with reusable:
        pass
    with pytest.raises(RuntimeError, match="already"):
        reusable.__enter__()
    with pytest.raises(RuntimeError, match="not active"):
        reusable.__exit__(None, None, None)
    with activate_context(object()), pytest.raises(RuntimeError, match="not a session"):
        session().__enter__()


def test_session_closes_every_reader_and_reports_cleanup_failure() -> None:
    class BrokenBody:
        def close(self) -> None:
            raise OSError("body cleanup failed")

    class BrokenReader:
        _body = BrokenBody()

        def close(self) -> None:
            raise OSError("reader cleanup failed")

    active = session()
    active.__enter__()
    active._readers.extend((BrokenReader(), BrokenReader()))  # type: ignore[arg-type]
    with pytest.raises(OSError, match="reader cleanup failed"):
        active.__exit__(None, None, None)
