# Provium Text Pipeline Example

[![Tests](https://github.com/Project-Provium/provium/actions/workflows/test.yml/badge.svg)](https://github.com/Project-Provium/provium/actions/workflows/test.yml)

This installable example demonstrates a catalog-discovered artifact pipeline:

- `DocumentV1` stores a UTF-8 document and loads or dumps `.txt` files.
- `TokensV1` stores a JSON list of tokens and dumps it as newline-delimited text.
- `TokenizeV1` reads a document and produces its whitespace-delimited tokens.

## Install

From the repository root:

```bash
python -m pip install -e "./packages/provium"
python -m pip install -e "./examples/provium-text-pipeline[test]"
```

## Run the pipeline

```bash
provium artifact load \
  provium_text_pipeline_example.DocumentV1 \
  document.txt \
  document.pa

provium execute \
  provium_text_pipeline_example.TokenizeV1 \
  --input source=document.pa \
  --output destination=tokens.pa

provium artifact dump tokens.pa tokens.txt
```

The loaded document starts a new lineage through Provium's internal load
procedure. The token artifact records the document as its input and
`TokenizeV1` as its producing procedure.

## Test

```bash
pytest
```

The tests exercise catalog discovery laziness and the complete CLI workflow,
including artifact transfer, procedure execution, output contents, and lineage.
