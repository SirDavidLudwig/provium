from __future__ import annotations

import json
from pathlib import Path

import pytest

from provium import (
    ArtifactCatalog,
    JsonArtifact,
    JsonArtifactReader,
    JsonArtifactWriter,
    Procedure,
    decode_header,
)


def test_json_artifact_round_trips_generic_json_without_registration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "value.pa"
    value = {
        "active": True,
        "items": [None, 1, 2.5, "text"],
        "nested": {"count": 3},
    }
    monkeypatch.setattr("provium.procedure.discover_catalogs", ArtifactCatalog)

    with Procedure("create", "1").execute():
        writer = JsonArtifact.create(path)
        assert isinstance(writer, JsonArtifactWriter)
        writer.write(value)

    with Procedure("read", "1").execute():
        reader = JsonArtifact.open(path)
        assert isinstance(reader, JsonArtifactReader)
        assert reader.read() == value

    header = decode_header(path.read_bytes())
    assert header.artifact_identifier == (
        f"{JsonArtifact.__module__}.{JsonArtifact.__qualname__}"
    )


def test_json_writer_uses_canonical_compact_encoding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "value.pa"
    monkeypatch.setattr("provium.procedure.discover_catalogs", ArtifactCatalog)

    with Procedure("create", "1").execute():
        JsonArtifact.create(path).write({"z": 1, "a": "é"})

    data = path.read_bytes()
    header = decode_header(data)
    body = data[header.body_offset : header.body_offset + header.body_length]
    assert body == b'{"a":"\xc3\xa9","z":1}'


@pytest.mark.parametrize(
    "value",
    [
        {1: "non-string key"},
        ("tuple",),
        float("nan"),
        object(),
    ],
)
def test_json_writer_rejects_values_outside_json_domain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    value: object,
) -> None:
    monkeypatch.setattr("provium.procedure.discover_catalogs", ArtifactCatalog)

    with (
        Procedure("create", "1").execute(),
        pytest.raises((TypeError, ValueError)),
    ):
        JsonArtifact.create(tmp_path / "invalid.pa").write(value)


def test_json_reader_rejects_malformed_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "value.pa"
    monkeypatch.setattr("provium.procedure.discover_catalogs", ArtifactCatalog)

    with Procedure("create", "1").execute():
        JsonArtifact.create(path).body.write(b"not-json")

    with (
        Procedure("read", "1").execute(),
        pytest.raises(json.JSONDecodeError),
    ):
        JsonArtifact.open(path).read()


def test_json_artifact_can_use_registered_identifier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "value.pa"
    catalog = ArtifactCatalog()
    catalog.register("provium.JsonV1", JsonArtifact)
    monkeypatch.setattr("provium.procedure.discover_catalogs", lambda: catalog)

    with Procedure("create", "1").execute():
        JsonArtifact.create(path).write([1, 2, 3])

    assert decode_header(path.read_bytes()).artifact_identifier == "provium.JsonV1"
