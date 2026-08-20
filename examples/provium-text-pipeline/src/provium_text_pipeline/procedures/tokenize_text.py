"""Tokenization procedure implementation."""

import re

from provium import Procedure, ProcedureProcessContext

from .catalog import TOKENIZE_DEFINITION, TokenizeConfig, TokenizeContract

_WORD_RE = re.compile(r"[A-Za-z0-9_]+")


class TokenizeText(
    Procedure[
        TokenizeConfig,
        TokenizeContract.SetupInputs,
        TokenizeContract.Inputs,
        TokenizeContract.Outputs,
    ]
):
    definition = TOKENIZE_DEFINITION

    def process(
        self,
        context: ProcedureProcessContext,
        configuration: TokenizeConfig,
        inputs: TokenizeContract.Inputs,
        outputs: TokenizeContract.Outputs,
    ) -> None:
        with inputs.text.open() as reader:
            raw_text = reader.read()

        tokens = _extract_tokens(raw_text, lowercase=configuration.lowercase)
        excluded = _read_stopwords(inputs.stopwords)

        filtered = [
            token
            for token in tokens
            if len(token) >= configuration.min_token_length and token not in excluded
        ]

        with outputs.tokens.open() as writer:
            writer.write(filtered)


def _extract_tokens(text: str, *, lowercase: bool) -> list[str]:
    value = text.lower() if lowercase else text
    return [match.group(0) for match in _WORD_RE.finditer(value)]


def _read_stopwords(stopwords: object | None) -> set[str]:
    if stopwords is None:
        return set()

    with stopwords.open() as reader:
        value = reader.read()

    return set(_extract_tokens(value, lowercase=True))


__all__ = ["TokenizeText"]
