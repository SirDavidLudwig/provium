from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from provium import ConfigurationSnapshot, Procedure


@dataclass(frozen=True)
class ExampleConfig:
    name: str
    values: tuple[int, ...]


class ExampleCodec:
    identifier = "example-config-v1"

    def encode(self, config: ExampleConfig) -> object:
        return {"name": config.name, "values": list(config.values)}

    def decode(self, value: object) -> ExampleConfig:
        if not isinstance(value, dict):
            raise TypeError("expected an object")
        return ExampleConfig(str(value["name"]), tuple(value["values"]))


def test_custom_codec_encodes_and_decodes_configuration() -> None:
    procedure = Procedure[ExampleConfig]("example", "1", ExampleCodec())
    config = ExampleConfig("sample", (1, 2, 3))

    snapshot = procedure.encode_config(config)

    assert snapshot == ConfigurationSnapshot(
        codec_identifier="example-config-v1",
        value={"name": "sample", "values": [1, 2, 3]},
    )
    assert procedure.decode_config(snapshot) == config


@pytest.mark.parametrize(
    "value",
    [
        None,
        {"nested": [None, True, False, "text", 1, 2.5]},
        ["value", {"key": 3}],
        "text",
        42,
        3.5,
        True,
        False,
    ],
)
def test_snapshot_preserves_json_values(value: object) -> None:
    snapshot = ConfigurationSnapshot("json-v1", value)

    assert ConfigurationSnapshot.from_json(snapshot.to_json()) == snapshot


@pytest.mark.parametrize(
    "value",
    [
        object(),
        {"invalid": object()},
        {1: "non-string-key"},
        float("inf"),
    ],
)
def test_snapshot_rejects_non_json_values(value: object) -> None:
    with pytest.raises((TypeError, ValueError), match="JSON"):
        ConfigurationSnapshot("json-v1", value)


class BrokenCodec:
    identifier = "broken-v1"

    def encode(self, config: object) -> object:
        return {"not-json": config}

    def decode(self, value: object) -> object:
        return value


def test_rejects_configuration_the_codec_cannot_encode() -> None:
    procedure = Procedure[object]("broken", "1", BrokenCodec())

    with pytest.raises(TypeError, match="JSON"):
        procedure.encode_config(object())


def test_procedure_without_configuration_needs_no_codec() -> None:
    procedure = Procedure("no-config", "1")

    assert procedure.name == "no-config"
    assert procedure.version == "1"
    assert procedure.config_codec is None
    assert procedure.encode_config(None) is None
    assert procedure.decode_config(None) is None


def test_non_none_configuration_requires_a_codec() -> None:
    procedure = Procedure[Any]("missing-codec", "1")

    with pytest.raises(TypeError, match="codec"):
        procedure.encode_config({"value": 1})
    with pytest.raises(TypeError, match="codec"):
        procedure.decode_config(ConfigurationSnapshot("json-v1", {"value": 1}))


def test_configured_procedure_requires_snapshot_when_decoding() -> None:
    procedure = Procedure[ExampleConfig]("example", "1", ExampleCodec())

    with pytest.raises(TypeError, match="snapshot"):
        procedure.decode_config(None)


def test_snapshot_codec_must_match_procedure_codec() -> None:
    procedure = Procedure[ExampleConfig]("example", "1", ExampleCodec())
    snapshot = ConfigurationSnapshot("other-v1", {"name": "sample", "values": []})

    with pytest.raises(ValueError, match="identifier"):
        procedure.decode_config(snapshot)


def test_procedure_identity_and_codec_identifier_are_validated() -> None:
    with pytest.raises(ValueError, match="name"):
        Procedure("", "1")
    with pytest.raises(ValueError, match="version"):
        Procedure("example", "")

    codec = ExampleCodec()
    object.__setattr__(codec, "identifier", "")
    with pytest.raises(ValueError, match="identifier"):
        Procedure("example", "1", codec)

    with pytest.raises(ValueError, match="codec_identifier"):
        ConfigurationSnapshot("", None)


def test_snapshot_rejects_invalid_serialized_shape() -> None:
    with pytest.raises(ValueError, match="snapshot"):
        ConfigurationSnapshot.from_json("[]")
    with pytest.raises(ValueError, match="snapshot"):
        ConfigurationSnapshot.from_json('{"codec_identifier":"json-v1"}')
