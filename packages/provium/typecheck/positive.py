"""Positive static typing contracts for Provium's generic public API."""

from __future__ import annotations

from typing import ClassVar, assert_type

from provium import (
    Artifact,
    ArtifactCatalog,
    ArtifactDefinition,
    ArtifactReadBinding,
    ArtifactReader,
    ArtifactWriteBinding,
    ArtifactWriter,
    Procedure,
    ProcedureCatalog,
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
    validate_procedure_configuration,
)


class ImageReader(ArtifactReader):
    pass


class ImageWriter(ArtifactWriter):
    pass


class ImageArtifact(Artifact[ImageReader, ImageWriter]):
    definition: ClassVar[ArtifactDefinition[ImageArtifact]]
    reader = ImageReader
    writer = ImageWriter


IMAGE_ARTIFACT: ArtifactDefinition[ImageArtifact] = ArtifactDefinition(
    identifier="example.ImageV1",
    target="example.artifacts:ImageArtifact",
    description="An image.",
)

ImageArtifact.definition = IMAGE_ARTIFACT

assert_type(ImageArtifact.bind_read("image.pa"), ArtifactReadBinding[ImageReader])
assert_type(ImageArtifact.bind_write("image.pa"), ArtifactWriteBinding[ImageWriter])
assert_type(IMAGE_ARTIFACT.resolve(), type[ImageArtifact])
assert_type(
    ArtifactCatalog().register(IMAGE_ARTIFACT), ArtifactDefinition[ImageArtifact]
)


class Config(ProcedureConfig):
    threshold: float = 0.5


assert_type(
    validate_procedure_configuration("example.DetectV1", Config, {}),
    Config,
)


class Contract(ProcedureContract[Config]):
    configuration = Config

    class SetupInputs(ProcedureInputs):
        pass

    class Inputs(ProcedureInputs):
        image = input(IMAGE_ARTIFACT)
        previous = optional_input(IMAGE_ARTIFACT)
        images = repeated_input(IMAGE_ARTIFACT, minimum=1)

    class Outputs(ProcedureOutputs):
        image = output(IMAGE_ARTIFACT)
        preview = optional_output(IMAGE_ARTIFACT)


def check_procedure_io_types(
    inputs: Contract.Inputs, outputs: Contract.Outputs
) -> None:
    assert_type(inputs.image, ArtifactReadBinding[ImageReader])
    assert_type(inputs.previous, ArtifactReadBinding[ImageReader] | None)
    assert_type(inputs.images, tuple[ArtifactReadBinding[ImageReader], ...])
    assert_type(outputs.image, ArtifactWriteBinding[ImageWriter])
    assert_type(outputs.preview, ArtifactWriteBinding[ImageWriter] | None)


class DetectProcedure(
    Procedure[Config, Contract.SetupInputs, Contract.Inputs, Contract.Outputs]
):
    definition: ClassVar[ProcedureDefinition[DetectProcedure]]


DETECT_PROCEDURE: ProcedureDefinition[DetectProcedure] = ProcedureDefinition(
    identifier="example.DetectV1",
    target="example.procedures:DetectProcedure",
    label="Detect",
    description="Detect objects.",
    contract=Contract,
)

DetectProcedure.definition = DETECT_PROCEDURE

assert_type(DETECT_PROCEDURE.resolve(), type[DetectProcedure])
assert_type(
    ProcedureCatalog().register(DETECT_PROCEDURE),
    ProcedureDefinition[DetectProcedure],
)
