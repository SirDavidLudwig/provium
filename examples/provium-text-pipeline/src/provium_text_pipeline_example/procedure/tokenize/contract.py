from provium import ProcedureContract, ProcedureInputs, ProcedureOutputs
from provium import input as input_field
from provium import output as output_field

from provium_text_pipeline_example.artifact import DOCUMENT, TOKENS


class TokenizeV1ProcedureContract(ProcedureContract[None]):
    class SetupInputs(ProcedureInputs):
        pass

    class Inputs(ProcedureInputs):
        source = input_field(DOCUMENT)

    class Outputs(ProcedureOutputs):
        destination = output_field(TOKENS)
