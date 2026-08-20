"""Tests for procedure configuration models."""

import json
from pathlib import Path
from types import MappingProxyType

import pytest
from pydantic import Field, ValidationError, field_validator

from provium import (
    ProcedureConfig,
    compose_configuration,
    load_json_configuration,
    load_yaml_configuration,
)


class ExampleConfig(ProcedureConfig):
    name: str
    retries: int = Field(default=1, ge=1)


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
