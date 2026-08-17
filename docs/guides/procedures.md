# Procedures and provenance

A `Procedure` describes a versioned processing step. Executing it establishes a
context in which opened artifacts become inputs and newly created artifacts
become outputs.

```python
from provium import JsonArtifact, Procedure

TRANSFORM = Procedure(name="transform", version="1")

with TRANSFORM.execute():
    source = JsonArtifact.open("source.pa")
    result = JsonArtifact.create("result.pa")
    result.write({"source": source.read()})
```

The output records both the procedure execution and the complete lineage of its
inputs. Procedure contexts finalize their outputs only when execution completes
successfully.

## Inspect lineage in Python

Every reader exposes the artifact header and lineage:

```python
from provium import JsonArtifact, session

with session():
    artifact = JsonArtifact.open("result.pa")
    print(artifact.identity)
    print(artifact.artifact_identifier)
    print(artifact.lineage.to_json())
```

Use `provium.open_artifact()` when the concrete type should be resolved from the
identifier stored in the artifact rather than selected in advance.

## Reuse inputs across procedures

A session records every artifact opened within it, even after its reader is
closed. Procedure executions inherit those inputs and establish a nested session
for artifacts used only during that execution.

## Persistent procedures

A persistent procedure prepares reusable state once and shares it across
multiple executions. This is useful when setup is expensive—for example, when a
model or lookup table should be loaded once before processing a batch of inputs.

Define a `setup` function on the procedure, then call the procedure to create a
lazy, configured instance:

```python
from provium import JsonArtifact, JsonArtifactReader, Procedure, session


def load_model(_: None) -> JsonArtifactReader:
    return JsonArtifact.open("model.pa")


PREDICT = Procedure[None, JsonArtifactReader](
    name="predict",
    version="1",
    setup=load_model,
)

predict = PREDICT(config=None)

with session():
    for input_path, output_path in (
        ("first.pa", "first-result.pa"),
        ("second.pa", "second-result.pa"),
    ):
        with predict as execution:
            # The setup reader persists, so rewind it before reading it again.
            execution.state.body.seek(0)
            model = execution.state.read()
            input_value = JsonArtifact.open(input_path).read()

            output = JsonArtifact.create(output_path)
            output.write({"model": model, "input": input_value})
```

The instance is lazy: `load_model` runs on the first `with predict` entry, not
when `predict` is created. It runs only once during the owning session, while
each context entry creates a fresh execution identity. Artifacts opened during
setup are included as inputs in every execution's lineage.

The outer `session()` owns the instance and its setup resources. When that
session exits, Provium closes the persistent readers and the instance becomes
unusable. A persistent instance cannot be moved to another session, entered
while it is already executing, or used to nest procedure executions.

The prepared state is available as `execution.state` during execution and as
`predict.state` between executions while the owning session remains open.
