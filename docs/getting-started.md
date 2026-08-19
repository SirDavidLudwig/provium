# Getting started

Provium requires Python 3.12 or newer.

## Installation

```bash
python -m pip install provium provium-cli
```

`provium` provides the core library. `provium-cli` provides the `provium`
command and the command plugin API.

## Create a provenance-aware workflow

Provium includes `JsonArtifact` for storing JSON-compatible values. This
example records a collection of measurements and produces a summary:

```python
from provium import JsonArtifact, Procedure

COLLECT = Procedure(name="collect", version="1")
SUMMARIZE = Procedure(name="summarize", version="1")

with COLLECT.execute():
    measurements = JsonArtifact.create("measurements.pa")
    measurements.write({"measurements": [12.5, 14.0, 13.5]})

with SUMMARIZE.execute():
    measurements = JsonArtifact.open("measurements.pa")
    payload = measurements.read()
    assert isinstance(payload, dict)
    values = payload["measurements"]
    assert isinstance(values, list)

    summary = JsonArtifact.create("summary.pa")
    summary.write(
        {
            "count": len(values),
            "minimum": min(values),
            "maximum": max(values),
            "average": round(sum(values) / len(values), 2),
        }
    )
```

When each context exits successfully, Provium closes its handles and finalizes
its output files. If a context exits with an exception, pending outputs are not
committed. Readers and writers are bound to their execution and cannot be used
after its context exits.

## Next steps

- Learn how to define [custom artifact types](guides/artifacts.md).
- Understand [procedures, sessions, and provenance](guides/procedures.md).
- Inspect results with the [command-line tools](guides/cli.md).
