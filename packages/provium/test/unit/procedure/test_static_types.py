from typing import Any, ClassVar, get_type_hints

from provium import (
    Procedure,
    ProcedureCatalog,
    ProcedureContract,
    ProcedureDefinition,
)


def test_procedure_and_definition_preserve_their_generic_types() -> None:
    configuration, setup_inputs, inputs, outputs = Procedure.__type_params__
    definition_annotations = get_type_hints(ProcedureDefinition)
    (procedure_type,) = ProcedureDefinition.__type_params__
    resolve_annotations = get_type_hints(
        ProcedureDefinition.resolve,
        localns={"ProcedureT": procedure_type},
    )

    assert get_type_hints(Procedure)["definition"] == ClassVar[ProcedureDefinition[Any]]
    assert configuration is not setup_inputs
    assert setup_inputs is not inputs
    assert inputs is not outputs
    assert procedure_type.__bound__ == Procedure[Any, Any, Any, Any]
    assert definition_annotations["contract"] == type[ProcedureContract[Any]]
    assert resolve_annotations["return"] == type[procedure_type]


def test_catalog_registration_preserves_the_concrete_procedure_type() -> None:
    (procedure_type,) = ProcedureCatalog.register.__type_params__
    annotations = get_type_hints(
        ProcedureCatalog.register,
        localns={"ProcedureT": procedure_type},
    )

    assert procedure_type.__bound__ == Procedure[Any, Any, Any, Any]
    assert annotations["definition"] == ProcedureDefinition[procedure_type]
    assert annotations["return"] == ProcedureDefinition[procedure_type]
