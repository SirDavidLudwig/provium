"""Artifact catalog for the text pipeline example package."""

from provium import ArtifactCatalog, ArtifactDefinition

from .raw_text import RawTextArtifact
from .token_list import TokenListArtifact
from .word_stats import WordStatsArtifact

RAW_TEXT_DEFINITION = ArtifactDefinition(
    "example.RawTextV1",
    "provium_text_pipeline.artifacts.raw_text:RawTextArtifact",
    "Plain UTF-8 text for downstream parsing.",
)

TOKEN_LIST_DEFINITION = ArtifactDefinition(
    "example.TokenListV1",
    "provium_text_pipeline.artifacts.token_list:TokenListArtifact",
    "Normalized token sequence payload.",
)

WORD_STATS_DEFINITION = ArtifactDefinition(
    "example.WordStatsV1",
    "provium_text_pipeline.artifacts.word_stats:WordStatsArtifact",
    "Word frequency counts keyed by token.",
)


RawTextArtifact.definition = RAW_TEXT_DEFINITION
TokenListArtifact.definition = TOKEN_LIST_DEFINITION
WordStatsArtifact.definition = WORD_STATS_DEFINITION


artifact_catalog = ArtifactCatalog()
artifact_catalog.register(RAW_TEXT_DEFINITION)
artifact_catalog.register(TOKEN_LIST_DEFINITION)
artifact_catalog.register(WORD_STATS_DEFINITION)


__all__ = [
    "RAW_TEXT_DEFINITION",
    "TOKEN_LIST_DEFINITION",
    "WORD_STATS_DEFINITION",
    "artifact_catalog",
]
