"""Procedure implementations for the text pipeline example package."""

from .aggregate_word_counts import AggregateWordCounts
from .catalog import (
    AGGREGATE_DEFINITION,
    TOKENIZE_DEFINITION,
    procedure_catalog,
)
from .tokenize_text import TokenizeText

__all__ = [
    "AGGREGATE_DEFINITION",
    "TOKENIZE_DEFINITION",
    "AggregateWordCounts",
    "TokenizeText",
    "procedure_catalog",
]
