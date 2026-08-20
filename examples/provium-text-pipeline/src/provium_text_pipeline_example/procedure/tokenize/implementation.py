from provium import Procedure

from .contract import TokenizeV1ProcedureContract
from .definition import TOKENIZE


class TokenizeV1Procedure(
    Procedure[
        None,
        TokenizeV1ProcedureContract.SetupInputs,
        TokenizeV1ProcedureContract.Inputs,
        TokenizeV1ProcedureContract.Outputs,
    ]
):
    definition = TOKENIZE

    def process(self, context, configuration, inputs, outputs):
        with inputs.source.open() as f:
            data = f.read()
        values = data.split()
        with outputs.destination.open() as f:
            f.write(values)
