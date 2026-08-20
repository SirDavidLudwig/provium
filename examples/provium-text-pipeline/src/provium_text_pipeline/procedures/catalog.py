"""Procedure catalog for the text pipeline example package."""

from provium import (
    ProcedureCatalog,
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

from provium_text_pipeline.artifacts import (
    RAW_TEXT_DEFINITION,
    TOKEN_LIST_DEFINITION,
    WORD_STATS_DEFINITION,
)


class TokenizeConfig(ProcedureConfig):
    """Configuration for tokenization behavior."""

    lowercase: bool = True
    min_token_length: int = 3


class TokenizeContract(ProcedureContract[TokenizeConfig]):
    configuration = TokenizeConfig

    class Inputs(ProcedureInputs):
        text = input(
            RAW_TEXT_DEFINITION,
            description="Raw text body to tokenize.",
        )
        stopwords = optional_input(
            RAW_TEXT_DEFINITION,
            description="Optional text file with one stopword per token boundary.",
        )

    class Outputs(ProcedureOutputs):
        tokens = output(
            TOKEN_LIST_DEFINITION,
            description="Normalized token list.",
        )


TOKENIZE_DEFINITION = ProcedureDefinition(
    "example.TokenizeTextV1",
    "provium_text_pipeline.procedures.tokenize_text:TokenizeText",
    "Tokenize text",
    "Normalize and tokenize raw UTF-8 text into an ordered token list.",
    TokenizeContract,
)


class AggregateConfig(ProcedureConfig):
    """Configuration for output truncation."""

    top_n: int = 0


class AggregateContract(ProcedureContract[AggregateConfig]):
    configuration = AggregateConfig

    class Inputs(ProcedureInputs):
        token_lists = repeated_input(
            TOKEN_LIST_DEFINITION,
            minimum=1,
            description="One or more token list inputs to merge.",
        )
        previous = optional_input(
            WORD_STATS_DEFINITION,
            description="Optional prior aggregate to increment into.",
        )

    class Outputs(ProcedureOutputs):
        counts = output(
            WORD_STATS_DEFINITION,
            description="Aggregated token frequencies.",
        )


AGGREGATE_DEFINITION = ProcedureDefinition(
    "example.AggregateWordCountsV1",
    "provium_text_pipeline.procedures.aggregate_word_counts:AggregateWordCounts",
    "Aggregate word counts",
    "Aggregate token frequencies across one or more token lists.",
    AggregateContract,
)

procedure_catalog = ProcedureCatalog()
procedure_catalog.register(TOKENIZE_DEFINITION)
procedure_catalog.register(AGGREGATE_DEFINITION)


__all__ = [
    "AGGREGATE_DEFINITION",
    "TOKENIZE_DEFINITION",
    "AggregateConfig",
    "AggregateContract",
    "TokenizeConfig",
    "TokenizeContract",
    "procedure_catalog",
]
