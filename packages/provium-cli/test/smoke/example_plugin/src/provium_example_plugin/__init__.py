"""External procedure plugin used by the installed-wheel smoke test."""

from provium import Procedure, ProcedureCatalog, ProcedureContract, ProcedureDefinition


class Contract(ProcedureContract[None]):
    configuration = None


DEFINITION = ProcedureDefinition(
    "smoke.EmptyV1",
    "provium_example_plugin:Implementation",
    "Empty smoke procedure",
    "Exercise an installed external procedure catalog.",
    Contract,
)


class Implementation(
    Procedure[None, Contract.SetupInputs, Contract.Inputs, Contract.Outputs]
):
    definition = DEFINITION

    def process(self, context, configuration, inputs, outputs):
        pass


catalog = ProcedureCatalog()
catalog.register(DEFINITION)
