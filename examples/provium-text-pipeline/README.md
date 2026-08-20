# Provium Text Pipeline Example

This example package demonstrates a full catalog-driven setup:

- three custom artifact types (`RawTextV1`, `TokenListV1`, `WordStatsV1`)
- two procedures
  - `TokenizeTextV1`: normalize and tokenize raw text into a token list
  - `AggregateWordCountsV1`: combine one or more token lists into frequency stats
- one artifact catalog and one procedure catalog registered through `pyproject.toml`

## Install as a local package

```bash
pip install -e .
```

## Run from Python

```python
from provium import ProcedureExecutor
from provium_text_pipeline.artifacts import RAW_TEXT_DEFINITION, TOKEN_LIST_DEFINITION
from provium_text_pipeline.procedures import TOKENIZE_DEFINITION

result = ProcedureExecutor().execute(
    TOKENIZE_DEFINITION,
    configuration_layers=({"lowercase": True, "min_token_length": 3},),
    inputs={"text": RAW_TEXT_DEFINITION.resolve().bind_read("input.pa")},
    outputs={"tokens": TOKEN_LIST_DEFINITION.resolve().bind_write("tokens.pa")},
)
```

The input path must contain a `RawTextV1` Provium artifact. After creating one,
the same procedure can be discovered and executed through the installed CLI:

```bash
provium procedure show example.TokenizeTextV1 --resolve
provium execute example.TokenizeTextV1 \
  --config tokenize.json \
  --input text=input.pa \
  --output tokens=tokens.pa
```
