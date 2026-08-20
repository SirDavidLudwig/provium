"""Lightweight definitions and contracts for the integration test pipeline."""

from provium import (
    ArtifactDefinition,
    ProcedureConfig,
    ProcedureContract,
    ProcedureDefinition,
    ProcedureInputs,
    ProcedureOutputs,
    input,
    optional_input,
    optional_output,
    output,
    repeated_input,
)

TEXT_ARTIFACT = ArtifactDefinition(
    "test.TextV1",
    "support.provium_test_pipeline.artifacts:TextArtifact",
    "A small UTF-8 text artifact used by integration tests.",
)


class SourceConfig(ProcedureConfig):
    """Configuration for a source artifact."""

    text: str


class SourceContract(ProcedureContract[SourceConfig]):
    """Create one text artifact from configuration."""

    configuration = SourceConfig

    class Outputs(ProcedureOutputs):
        value = output(TEXT_ARTIFACT, description="Created text.")


class TransformConfig(ProcedureConfig):
    """Configuration applied around the combined input text."""

    prefix: str = ""
    suffix: str = ""


class TransformContract(ProcedureContract[TransformConfig]):
    """Combine setup, required, optional, and repeated text inputs."""

    configuration = TransformConfig

    class SetupInputs(ProcedureInputs):
        setup = input(TEXT_ARTIFACT, description="Reusable setup text.")

    class Inputs(ProcedureInputs):
        required = input(TEXT_ARTIFACT, description="Required invocation text.")
        optional = optional_input(TEXT_ARTIFACT, description="Optional text.")
        repeated = repeated_input(
            TEXT_ARTIFACT,
            minimum=1,
            maximum=4,
            description="Ordered repeated text.",
        )

    class Outputs(ProcedureOutputs):
        transformed = output(TEXT_ARTIFACT, description="Combined text.")
        summary = output(TEXT_ARTIFACT, description="Input count and length summary.")


class FailingContract(ProcedureContract[None]):
    """Write a partial output and then fail."""

    configuration = None

    class Inputs(ProcedureInputs):
        source = input(TEXT_ARTIFACT)

    class Outputs(ProcedureOutputs):
        result = output(TEXT_ARTIFACT)
        secondary = optional_output(TEXT_ARTIFACT)


SOURCE_PROCEDURE = ProcedureDefinition(
    "test.SourceTextV1",
    "support.provium_test_pipeline.procedures:SourceProcedure",
    "Source text",
    "Create a deterministic text artifact.",
    SourceContract,
)

TRANSFORM_PROCEDURE = ProcedureDefinition(
    "test.TransformTextV1",
    "support.provium_test_pipeline.procedures:TransformProcedure",
    "Transform text",
    "Combine several text inputs using reusable setup state.",
    TransformContract,
)

FAILING_PROCEDURE = ProcedureDefinition(
    "test.FailingTextV1",
    "support.provium_test_pipeline.procedures:FailingProcedure",
    "Failing text",
    "Write partial output before raising a deterministic error.",
    FailingContract,
)
