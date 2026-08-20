"""Artifact modules for the text pipeline example package."""

from .catalog import (
    RAW_TEXT_DEFINITION,
    TOKEN_LIST_DEFINITION,
    WORD_STATS_DEFINITION,
    artifact_catalog,
)
from .raw_text import RawTextArtifact
from .token_list import TokenListArtifact
from .word_stats import WordStatsArtifact

__all__ = [
    "RAW_TEXT_DEFINITION",
    "TOKEN_LIST_DEFINITION",
    "WORD_STATS_DEFINITION",
    "RawTextArtifact",
    "TokenListArtifact",
    "WordStatsArtifact",
    "artifact_catalog",
]
