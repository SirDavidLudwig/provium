"""Guarded negative static typing contracts for Provium's generic API."""

from __future__ import annotations

from typing import ClassVar

from provium import (
    Artifact,
    ArtifactDefinition,
    ArtifactReader,
    ArtifactWriter,
    Procedure,
    ProcedureContract,
    ProcedureDefinition,
    ProcedureInputs,
    ProcedureOutputs,
)


class Reader(ArtifactReader):
    pass


class Writer(ArtifactWriter):
    pass


class OtherReader(ArtifactReader):
    pass


class ExampleArtifact(Artifact[Reader, Writer]):
    definition: ClassVar[ArtifactDefinition[ExampleArtifact]]
    reader = Reader
    writer = Writer


class WrongReaderArtifact(Artifact[Reader, Writer]):
    definition: ClassVar[ArtifactDefinition[WrongReaderArtifact]]
    reader = OtherReader  # pyright: ignore[reportAssignmentType]
    writer = Writer


class OtherArtifact(Artifact[Reader, Writer]):
    definition: ClassVar[ArtifactDefinition[OtherArtifact]]
    reader = Reader
    writer = Writer


OTHER_ARTIFACT: ArtifactDefinition[OtherArtifact] = ArtifactDefinition(
    "example.OtherV1",
    "example.artifacts:OtherArtifact",
    "Another artifact.",
)

wrong_artifact_definition: ArtifactDefinition[ExampleArtifact] = OTHER_ARTIFACT  # pyright: ignore[reportAssignmentType]


class Config:
    pass


class SetupInputs(ProcedureInputs):
    pass


class Inputs(ProcedureInputs):
    pass


class Outputs(ProcedureOutputs):
    pass


class Contract(ProcedureContract[Config]):
    pass


class ExampleProcedure(Procedure[Config, SetupInputs, Inputs, Outputs]):
    definition: ClassVar[ProcedureDefinition[ExampleProcedure]]


class OtherProcedure(Procedure[Config, SetupInputs, Inputs, Outputs]):
    definition: ClassVar[ProcedureDefinition[OtherProcedure]]


OTHER_PROCEDURE: ProcedureDefinition[OtherProcedure] = ProcedureDefinition(
    "example.OtherV1",
    "example.procedures:OtherProcedure",
    "Other",
    None,
    Contract,
)

wrong_procedure_definition: ProcedureDefinition[ExampleProcedure] = OTHER_PROCEDURE  # pyright: ignore[reportAssignmentType]
