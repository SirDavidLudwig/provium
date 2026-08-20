import pytest

from provium import ProcedureCatalog, ProcedureContract, ProcedureDefinition


class Contract(ProcedureContract[object]):
    pass


DEFINITION = ProcedureDefinition(
    "example.ExampleV1",
    "example.procedures:ExampleProcedure",
    "Example",
    None,
    Contract,
)


def test_catalog_registers_and_resolves_procedure_definitions() -> None:
    catalog = ProcedureCatalog()

    assert catalog.register(DEFINITION) is DEFINITION
    assert catalog.resolve("example.ExampleV1") is DEFINITION
    assert dict(catalog.definitions) == {"example.ExampleV1": DEFINITION}


def test_catalog_rejects_invalid_and_duplicate_definitions() -> None:
    catalog = ProcedureCatalog()
    with pytest.raises(TypeError, match="ProcedureDefinition"):
        catalog.register(object())  # type: ignore[arg-type]

    catalog.register(DEFINITION)
    with pytest.raises(ValueError, match="already registered"):
        catalog.register(DEFINITION)


def test_catalog_definitions_are_read_only() -> None:
    catalog = ProcedureCatalog()
    catalog.register(DEFINITION)

    with pytest.raises(TypeError):
        catalog.definitions["other"] = DEFINITION  # type: ignore[index]


def test_catalog_raises_for_an_unknown_identifier() -> None:
    with pytest.raises(KeyError):
        ProcedureCatalog().resolve("example.UnknownV1")
