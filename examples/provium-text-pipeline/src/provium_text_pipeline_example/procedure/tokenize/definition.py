from provium import ProcedureDefinition

_path = "provium_text_pipeline_example.procedure.tokenize"

TOKENIZE = ProcedureDefinition(
    identifier="provium_text_pipeline_example.TokenizeV1",
    label="Tokenize",
    target=f"{_path}.implementation:TokenizeV1Procedure",
    contract=f"{_path}.contract:TokenizeV1ProcedureContract",
    description="Tokenize words",
)
