"""Example Provium plugin package for text workflows."""

from .artifacts import (
    RAW_TEXT_DEFINITION,
    TOKEN_LIST_DEFINITION,
    WORD_STATS_DEFINITION,
    RawTextArtifact,
    TokenListArtifact,
    WordStatsArtifact,
)
from .procedures import (
    AggregateWordCounts,
    TokenizeText,
)
from .procedures.catalog import AGGREGATE_DEFINITION, TOKENIZE_DEFINITION

__all__ = [
    "AGGREGATE_DEFINITION",
    "RAW_TEXT_DEFINITION",
    "TOKENIZE_DEFINITION",
    "TOKEN_LIST_DEFINITION",
    "WORD_STATS_DEFINITION",
    "AggregateWordCounts",
    "RawTextArtifact",
    "TokenListArtifact",
    "TokenizeText",
    "WordStatsArtifact",
]
