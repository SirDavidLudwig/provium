# Provium

Provium is a small standalone Python package for typed binary artifacts with
automatic provenance.

Provium artifact files use the `.pa` extension.

Artifact I/O occurs only inside a scoped procedure execution. Every artifact
opened in that scope is tracked automatically as an input, and every artifact
created in that scope is tracked automatically as an output. Users do not
construct or supply lineage manually.

## Status

Provium is in pre-alpha development. Implementation follows the test-driven
sequence in [`provium_tdd_plan.md`](provium_tdd_plan.md), with each step reviewed
before the next begins.

## Development setup

Provium requires Python 3.12 or newer and has no required runtime dependencies.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[test]'
```

Run the test suite with:

```bash
pytest
```

The project configuration requires 100% statement and branch coverage for the
`provium` package.

## Planned API

```python
from provium import Procedure

ADD = Procedure(name="add", version="1")

with ADD.execute():
    left = Integer.open("left.pa")
    right = Integer.open("right.pa")
    result = Integer.create("sum.pa")
    result.write(left.read() + right.read())
```

The API shown above is the target design and is not implemented yet.
