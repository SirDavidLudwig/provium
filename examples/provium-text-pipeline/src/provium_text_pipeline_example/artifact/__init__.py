from __future__ import annotations

from typing import TYPE_CHECKING

from provium import ArtifactCatalog, ArtifactDefinition

_path = "provium_text_pipeline_example"

if TYPE_CHECKING:
    from .document import DocumentV1Artifact
    from .tokens import TokensV1Artifact

DOCUMENT: ArtifactDefinition[DocumentV1Artifact] = ArtifactDefinition(
    identifier=f"{_path}.DocumentV1",
    target=f"{_path}.artifact.document:DocumentV1Artifact",
    description="An artifact containing a text document",
)

TOKENS: ArtifactDefinition[TokensV1Artifact] = ArtifactDefinition(
    identifier=f"{_path}.TokensV1",
    target=f"{_path}.artifact.tokens:TokensV1Artifact",
    description="An artifact containing word tokens",
)


catalog = ArtifactCatalog()
catalog.register(DOCUMENT)
catalog.register(TOKENS)
