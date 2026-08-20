"""Lightweight contracts for the installed example plugin."""

from provium import (
    ArtifactDefinition,
    ProcedureConfig,
    ProcedureContract,
    ProcedureDefinition,
    ProcedureInputs,
    ProcedureOutputs,
    input,
    optional_input,
    output,
    repeated_input,
)

TEXT_ARTIFACT = ArtifactDefinition(
    "smoke.TextV1",
    "provium_example_plugin.artifacts:TextArtifact",
    "A UTF-8 text artifact.",
)


class SourceConfig(ProcedureConfig):
    text: str


class SourceContract(ProcedureContract[SourceConfig]):
    configuration = SourceConfig

    class Outputs(ProcedureOutputs):
        value = output(TEXT_ARTIFACT)


class TransformConfig(ProcedureConfig):
    prefix: str = ""
    suffix: str = ""


class TransformContract(ProcedureContract[TransformConfig]):
    configuration = TransformConfig

    class SetupInputs(ProcedureInputs):
        setup = input(TEXT_ARTIFACT)

    class Inputs(ProcedureInputs):
        required = input(TEXT_ARTIFACT)
        optional = optional_input(TEXT_ARTIFACT)
        repeated = repeated_input(TEXT_ARTIFACT, minimum=1, maximum=4)

    class Outputs(ProcedureOutputs):
        transformed = output(TEXT_ARTIFACT)
        summary = output(TEXT_ARTIFACT)


class FailingContract(ProcedureContract[None]):
    configuration = None

    class Inputs(ProcedureInputs):
        source = input(TEXT_ARTIFACT)

    class Outputs(ProcedureOutputs):
        result = output(TEXT_ARTIFACT)


SOURCE_PROCEDURE = ProcedureDefinition(
    "smoke.SourceTextV1",
    "provium_example_plugin.procedures:SourceProcedure",
    "Source text",
    "Create a configured text artifact.",
    SourceContract,
)
TRANSFORM_PROCEDURE = ProcedureDefinition(
    "smoke.TransformTextV1",
    "provium_example_plugin.procedures:TransformProcedure",
    "Transform text",
    "Combine setup and processing text artifacts.",
    TransformContract,
)
FAILING_PROCEDURE = ProcedureDefinition(
    "smoke.FailingTextV1",
    "provium_example_plugin.procedures:FailingProcedure",
    "Failing text",
    "Write partial output and fail.",
    FailingContract,
)
