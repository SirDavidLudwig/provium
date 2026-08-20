"""Tests for procedure configuration models."""

import json
import os
import subprocess
import sys
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType

import pytest
from pydantic import BaseModel, Field, ValidationError, field_validator

from provium import (
    ConfigurationSnapshot,
    ProcedureConfig,
    compose_configuration,
    load_json_configuration,
    load_yaml_configuration,
)


class ExampleConfig(ProcedureConfig):
    name: str
    retries: int = Field(default=1, ge=1)


def canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def test_configuration_uses_pydantic_validation() -> None:
    configuration = ExampleConfig(name="example", retries="2")  # type: ignore[arg-type]

    assert configuration.name == "example"
    assert configuration.retries == 2


def test_configuration_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ExampleConfig(name="example", unknown=True)  # type: ignore[call-arg]


def test_configuration_is_frozen() -> None:
    configuration = ExampleConfig(name="example")

    with pytest.raises(ValidationError, match="Instance is frozen"):
        configuration.retries = 2


def test_configuration_validates_default_values() -> None:
    class InvalidDefaultConfig(ProcedureConfig):
        retries: int = Field(default=0, ge=1)

    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        InvalidDefaultConfig()


def test_configuration_supports_custom_pydantic_validators() -> None:
    class NormalizedConfig(ProcedureConfig):
        name: str

        @field_validator("name")
        @classmethod
        def normalize_name(cls, value: str) -> str:
            return value.strip().lower()

    assert NormalizedConfig(name=" Example ").name == "example"


def test_configuration_layers_merge_nested_mappings_recursively() -> None:
    composed = compose_configuration(
        [
            {"model": {"name": "small", "options": {"device": "cpu"}}},
            {"model": {"options": {"precision": "half"}}},
        ]
    )

    assert composed == {
        "model": {
            "name": "small",
            "options": {"device": "cpu", "precision": "half"},
        }
    }


@pytest.mark.parametrize("replacement", [2, [2], (2,), None])
def test_configuration_layers_replace_non_mapping_values(replacement: object) -> None:
    assert compose_configuration(
        [{"value": {"nested": True}}, {"value": replacement}]
    ) == {"value": replacement}


def test_configuration_mapping_replaces_an_existing_non_mapping() -> None:
    assert compose_configuration([{"value": 1}, {"value": {"nested": True}}]) == {
        "value": {"nested": True}
    }


def test_configuration_composition_does_not_mutate_or_alias_layers() -> None:
    first = {"nested": {"values": [1], "preserved": True}}
    second = {"nested": {"values": [2]}}

    composed = compose_configuration([first, second])
    composed["nested"]["values"].append(3)  # type: ignore[index, union-attr]

    assert first == {"nested": {"values": [1], "preserved": True}}
    assert second == {"nested": {"values": [2]}}


def test_configuration_composition_accepts_a_one_shot_iterable() -> None:
    layers = ({"value": value} for value in range(3))

    assert compose_configuration(layers) == {"value": 2}


def test_configuration_composition_accepts_nested_read_only_mappings() -> None:
    layer = MappingProxyType(
        {"nested": MappingProxyType({"preserved": True, "value": 1})}
    )

    assert compose_configuration([layer, {"nested": {"value": 2}}]) == {
        "nested": {"preserved": True, "value": 2}
    }


def test_configuration_composition_rejects_recursive_mappings() -> None:
    layer: dict[str, object] = {}
    layer["recursive"] = layer

    with pytest.raises(ValueError, match="recursive mapping"):
        compose_configuration([layer])


def test_configuration_composition_rejects_recursive_sequences() -> None:
    recursive: list[object] = []
    recursive.append(recursive)

    with pytest.raises(ValueError, match="recursive sequence"):
        compose_configuration([{"value": recursive}])


def test_json_configuration_loads_an_object(tmp_path: Path) -> None:
    path = tmp_path / "configuration.json"
    path.write_text(
        json.dumps({"name": "café", "nested": {"enabled": True}}),
        encoding="utf-8",
    )

    assert load_json_configuration(path) == {
        "name": "café",
        "nested": {"enabled": True},
    }


@pytest.mark.parametrize("value", [None, True, 1, "value", [1]])
def test_json_configuration_rejects_a_non_object_root(
    tmp_path: Path, value: object
) -> None:
    path = tmp_path / "configuration.json"
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(TypeError, match="root must be an object"):
        load_json_configuration(path)


def test_json_configuration_preserves_decode_errors(tmp_path: Path) -> None:
    path = tmp_path / "configuration.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        load_json_configuration(path)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_json_configuration_rejects_non_finite_numbers(
    tmp_path: Path, constant: str
) -> None:
    path = tmp_path / "configuration.json"
    path.write_text(f'{{"value": {constant}}}', encoding="utf-8")

    with pytest.raises(json.JSONDecodeError, match="non-finite number"):
        load_json_configuration(path)


def test_json_configuration_accepts_string_and_path_like_paths(
    tmp_path: Path,
) -> None:
    path = tmp_path / "configuration.json"
    path.write_text("{}", encoding="utf-8")

    assert load_json_configuration(str(path)) == {}
    assert load_json_configuration(path) == {}


def test_yaml_configuration_loads_a_mapping(tmp_path: Path) -> None:
    path = tmp_path / "configuration.yaml"
    path.write_text(
        "name: café\nnested:\n  enabled: true\n",
        encoding="utf-8",
    )

    assert load_yaml_configuration(path) == {
        "name": "café",
        "nested": {"enabled": True},
    }


@pytest.mark.parametrize("document", ["null\n", "true\n", "1\n", "value\n", "- 1\n"])
def test_yaml_configuration_rejects_a_non_mapping_root(
    tmp_path: Path, document: str
) -> None:
    path = tmp_path / "configuration.yaml"
    path.write_text(document, encoding="utf-8")

    with pytest.raises(TypeError, match="root must be a mapping"):
        load_yaml_configuration(path)


def test_yaml_configuration_rejects_non_string_root_keys(tmp_path: Path) -> None:
    path = tmp_path / "configuration.yaml"
    path.write_text("1: value\n", encoding="utf-8")

    with pytest.raises(TypeError, match="root keys must be strings"):
        load_yaml_configuration(path)


def test_yaml_configuration_reports_its_optional_dependency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "configuration.yaml"
    path.write_text("{}", encoding="utf-8")

    def missing_yaml(name: str) -> object:
        assert name == "yaml"
        raise ModuleNotFoundError(name="yaml")

    monkeypatch.setattr("provium.procedure.config.import_module", missing_yaml)

    with pytest.raises(RuntimeError, match=r"provium\[yaml\]"):
        load_yaml_configuration(path)


def test_yaml_configuration_preserves_transitive_import_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "configuration.yaml"
    path.write_text("{}", encoding="utf-8")
    error = ModuleNotFoundError(name="yaml_dependency")

    def broken_yaml(name: str) -> object:
        assert name == "yaml"
        raise error

    monkeypatch.setattr("provium.procedure.config.import_module", broken_yaml)

    with pytest.raises(ModuleNotFoundError) as raised:
        load_yaml_configuration(path)

    assert raised.value is error


def test_yaml_configuration_preserves_parser_errors(tmp_path: Path) -> None:
    import yaml

    path = tmp_path / "configuration.yaml"
    path.write_text("value: [", encoding="utf-8")

    with pytest.raises(yaml.YAMLError):
        load_yaml_configuration(path)


def test_yaml_configuration_accepts_string_and_path_like_paths(
    tmp_path: Path,
) -> None:
    path = tmp_path / "configuration.yaml"
    path.write_text("{}", encoding="utf-8")

    assert load_yaml_configuration(str(path)) == {}
    assert load_yaml_configuration(path) == {}


class SnapshotConfig(ProcedureConfig):
    name: str = "café"
    retries: int = Field(default=2, alias="retryCount")
    optional: str | None = None


def test_configuration_snapshot_is_canonical_and_includes_defaults() -> None:
    snapshot = ConfigurationSnapshot.from_configuration(SnapshotConfig())
    expected_value = {"name": "café", "optional": None, "retryCount": 2}

    assert snapshot.model_target == f"{__name__}:SnapshotConfig"
    assert snapshot.value == expected_value
    assert snapshot.value_digest == canonical_digest(expected_value)
    assert snapshot.schema_digest == canonical_digest(
        SnapshotConfig.model_json_schema()
    )


def test_configuration_snapshot_matches_explicit_default_values() -> None:
    implicit = ConfigurationSnapshot.from_configuration(SnapshotConfig())
    explicit = ConfigurationSnapshot.from_configuration(
        SnapshotConfig(name="café", retryCount=2, optional=None)
    )

    assert implicit == explicit


def test_configuration_snapshot_is_stable_across_hash_seeds() -> None:
    script = """
from provium import ConfigurationSnapshot, ProcedureConfig

class SetConfig(ProcedureConfig):
    values: set[str]

print(ConfigurationSnapshot.from_configuration(
    SetConfig(values={"alpha", "beta", "gamma"})
).value_digest)
"""
    digests = {
        subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            env={**os.environ, "PYTHONHASHSEED": str(seed)},
            text=True,
        ).stdout.strip()
        for seed in range(1, 5)
    }

    assert len(digests) == 1


def test_nested_model_snapshot_is_stable_across_hash_seeds() -> None:
    script = """
from pydantic import BaseModel
from provium import ConfigurationSnapshot, ProcedureConfig

class NestedModel(BaseModel):
    values: set[str]

class NestedConfig(ProcedureConfig):
    nested: NestedModel

print(ConfigurationSnapshot.from_configuration(NestedConfig(
    nested=NestedModel(values={"alpha", "beta", "gamma"})
)).value_digest)
"""
    digests = {
        subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            env={**os.environ, "PYTHONHASHSEED": str(seed)},
            text=True,
        ).stdout.strip()
        for seed in range(1, 5)
    }

    assert len(digests) == 1


def test_custom_model_serializer_snapshot_is_stable_across_hash_seeds() -> None:
    script = """
from pydantic import model_serializer
from provium import ConfigurationSnapshot, ProcedureConfig

class SerializedConfig(ProcedureConfig):
    values: set[str]

    @model_serializer
    def serialize_model(self) -> dict[str, object]:
        return {"renamed": self.values}

print(ConfigurationSnapshot.from_configuration(
    SerializedConfig(values={"alpha", "beta", "gamma"})
).value_digest)
"""
    digests = {
        subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            env={**os.environ, "PYTHONHASHSEED": str(seed)},
            text=True,
        ).stdout.strip()
        for seed in range(1, 5)
    }

    assert len(digests) == 1


def test_configuration_snapshot_correlates_a_single_renamed_field() -> None:
    from pydantic import model_serializer

    class RenamedConfig(ProcedureConfig):
        values: set[str]

        @model_serializer(when_used="json")
        def serialize_model(self) -> dict[str, object]:
            return {"renamed": self.values}

    snapshot = ConfigurationSnapshot.from_configuration(
        RenamedConfig(values={"gamma", "alpha", "beta"})
    )

    assert snapshot.value == {"renamed": ["alpha", "beta", "gamma"]}


def test_configuration_snapshot_supports_a_shape_changing_model_serializer() -> None:
    from pydantic import model_serializer

    class CombinedConfig(ProcedureConfig):
        first: int
        second: int

        @model_serializer(when_used="json")
        def serialize_model(self) -> dict[str, int]:
            return {"total": self.first + self.second}

    snapshot = ConfigurationSnapshot.from_configuration(
        CombinedConfig(first=2, second=3)
    )

    assert snapshot.value == {"total": 5}


def test_configuration_snapshot_supports_a_shape_changing_field_serializer() -> None:
    from pydantic import field_serializer

    class TruncatedConfig(ProcedureConfig):
        values: list[int]
        tags: set[str]

        @field_serializer("values", when_used="json")
        def serialize_values(self, values: list[int]) -> list[int]:
            return values[:1]

        @field_serializer("tags", when_used="json")
        def serialize_tags(self, tags: set[str]) -> list[str]:
            return [min(tags)]

    snapshot = ConfigurationSnapshot.from_configuration(
        TruncatedConfig(values=[1, 2, 3], tags={"alpha", "beta"})
    )

    assert snapshot.value == {"tags": ["alpha"], "values": [1]}


def test_configuration_snapshot_correlates_reordered_serialized_fields_by_name() -> (
    None
):
    from pydantic import model_serializer

    class ReorderedConfig(ProcedureConfig):
        unordered: set[str]
        ordered: list[str]

        @model_serializer(when_used="json")
        def serialize_model(self) -> dict[str, object]:
            return {"ordered": self.ordered, "unordered": self.unordered}

    snapshot = ConfigurationSnapshot.from_configuration(
        ReorderedConfig(
            unordered={"gamma", "alpha", "beta"},
            ordered=["gamma", "alpha", "beta"],
        )
    )

    assert snapshot.value == {
        "ordered": ["gamma", "alpha", "beta"],
        "unordered": ["alpha", "beta", "gamma"],
    }


def test_configuration_snapshot_does_not_guess_partially_replaced_fields() -> None:
    from pydantic import model_serializer

    class ReplacedConfig(ProcedureConfig):
        unordered: set[str]
        preserved: int

        @model_serializer(when_used="json")
        def serialize_model(self) -> dict[str, object]:
            return {
                "preserved": self.preserved,
                "added": ["gamma", "alpha", "beta"],
            }

    snapshot = ConfigurationSnapshot.from_configuration(
        ReplacedConfig(unordered={"gamma", "alpha", "beta"}, preserved=1)
    )

    assert snapshot.value == {
        "added": ["gamma", "alpha", "beta"],
        "preserved": 1,
    }


def test_configuration_snapshot_canonicalizes_unordered_collections() -> None:
    class NestedCollectionModel(BaseModel):
        values: set[str]

    class CollectionConfig(ProcedureConfig):
        values: set[str]
        frozen_values: frozenset[str]
        ordered_values: list[str]
        nested_values: dict[str, frozenset[str]]
        tuple_values: tuple[str, ...]
        nested_model: NestedCollectionModel

    snapshot = ConfigurationSnapshot.from_configuration(
        CollectionConfig(
            values={"gamma", "alpha", "beta"},
            frozen_values=frozenset({"gamma", "alpha", "beta"}),
            ordered_values=["gamma", "alpha", "beta"],
            nested_values={"inner": frozenset({"gamma", "alpha", "beta"})},
            tuple_values=("gamma", "alpha", "beta"),
            nested_model=NestedCollectionModel(values={"gamma", "alpha", "beta"}),
        )
    )

    assert snapshot.value == {
        "frozen_values": ["alpha", "beta", "gamma"],
        "nested_values": {"inner": ["alpha", "beta", "gamma"]},
        "nested_model": {"values": ["alpha", "beta", "gamma"]},
        "ordered_values": ["gamma", "alpha", "beta"],
        "tuple_values": ["gamma", "alpha", "beta"],
        "values": ["alpha", "beta", "gamma"],
    }


def test_configuration_snapshot_is_frozen() -> None:
    snapshot = ConfigurationSnapshot.from_configuration(SnapshotConfig())

    with pytest.raises(AttributeError):
        snapshot.value_digest = "different"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_configuration_snapshot_rejects_non_finite_numbers(value: float) -> None:
    class FloatConfig(ProcedureConfig):
        value: float

    with pytest.raises(ValueError, match="finite"):
        ConfigurationSnapshot.from_configuration(FloatConfig(value=value))


@pytest.mark.parametrize("key", [float("nan"), float("inf"), float("-inf")])
def test_configuration_snapshot_rejects_non_finite_mapping_keys(key: float) -> None:
    class MappingConfig(ProcedureConfig):
        values: dict[float, str]

    with pytest.raises(ValueError, match="finite"):
        ConfigurationSnapshot.from_configuration(MappingConfig(values={key: "value"}))
