"""Positive static typing contracts for Provium's generic public API."""

from __future__ import annotations

from typing import ClassVar, assert_type

from provium import (
    Artifact,
    ArtifactCatalog,
    ArtifactDefinition,
    ArtifactReader,
    ArtifactWriter,
    Procedure,
    ProcedureCatalog,
    ProcedureConfig,
    ProcedureContract,
    ProcedureDefinition,
    ProcedureInputs,
    ProcedureOutputs,
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
        pass

    class Outputs(ProcedureOutputs):
        pass


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
