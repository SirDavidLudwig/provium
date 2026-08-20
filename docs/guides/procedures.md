# Procedures and provenance

Procedures are discoverable, typed classes. A lightweight contract describes
configuration and artifact ports without importing the implementation; a
`ProcedureDefinition` connects that contract to its plugin class.

## Define a contract

```python
from provium import (
    ProcedureConfig, ProcedureContract, ProcedureInputs, ProcedureOutputs,
    input, optional_input, output, repeated_input,
)

class DetectionConfig(ProcedureConfig):
    threshold: float = 0.5

class DetectContract(ProcedureContract[DetectionConfig]):
    configuration = DetectionConfig

    class SetupInputs(ProcedureInputs):
        model = input(MODEL)

    class Inputs(ProcedureInputs):
        image = input(IMAGE)
        previous = optional_input(DETECTIONS)
        references = repeated_input(IMAGE, minimum=1)

    class Outputs(ProcedureOutputs):
        detections = output(DETECTIONS)
```

Fields infer their reader or writer binding type from the artifact definition.
Input/output records are immutable. Optional inputs become `None`; repeated
inputs become ordered tuples.

## Implement and register a procedure

```python
from provium import Procedure, ProcedureDefinition

DETECT = ProcedureDefinition(
    "example.DetectV1",
    "example_plugin.procedures:Detect",
    "Detect objects",
    "Run a model over an image.",
    "example_plugin.contracts:DetectContract",
)

class Detect(Procedure[
    DetectionConfig,
    DetectContract.SetupInputs,
    DetectContract.Inputs,
    DetectContract.Outputs,
]):
    definition = DETECT

    def setup(self, context, configuration, inputs):
        with inputs.model.open() as reader:
            self.model = reader.read()

    def process(self, context, configuration, inputs, outputs):
        context.cancellation.raise_if_cancelled()
        with inputs.image.open() as reader:
            image = reader.read()
        outputs.detections.open().write(run_model(self.model, image))
```

Publish a `ProcedureCatalog` through the `provium.procedure_catalogs` entry-point
group. Discovery loads the catalog but does not import the definition target
until resolution or execution is requested.

## Execute directly

`ProcedureExecutor.execute()` validates layered configuration and bindings,
runs setup and processing once, finalizes all outputs transactionally, records
lineage, and closes the implementation.

```python
from provium import ProcedureExecutor

result = ProcedureExecutor().execute(
    DETECT,
    configuration_layers=({"threshold": 0.7},),
    setup_inputs={"model": ModelArtifact.bind_read("model.pa")},
    inputs={
        "image": ImageArtifact.bind_read("image.pa"),
        "references": [ImageArtifact.bind_read("reference.pa")],
    },
    outputs={
        "detections": DetectionsArtifact.bind_write("detections.pa"),
    },
)
```

Use `prepare()` when setup state should be reused. A prepared instance executes
sequentially, rejects concurrent reentry, and owns setup resources until
`close()`.

## Execution services

Setup and processing contexts expose a temporary directory and a thread-safe
`CancellationToken`. The setup directory lasts until the prepared procedure is
closed. Each processing directory is fresh and removed after that invocation.
Cancellation is cooperative: Provium checks immediately before user processing,
and long-running procedures should check at useful interruption points.

## Imperative compatibility

For dynamic workflows that cannot use a declared callback, use the separate
`ImperativeProcedure` facade. Explicit bindings retain transactional writes and
provenance without overloading the typed `Procedure` base class.

```python
from provium import ImperativeProcedure

source = ImageArtifact.bind_read("source.pa")
destination = ImageArtifact.bind_write("copy.pa")
execution = ImperativeProcedure("example.CopyV1", "contract-digest").execute(
    inputs=(source,), outputs={"copy": destination},
)
with execution:
    with source.open() as reader:
        destination.open().write(reader.read())

print(execution.result.identity)
```

Migration note: the former `Procedure("name", "version")` value object is no
longer the public procedure type. Subclass `Procedure[...]` for declared plugins,
or use `ImperativeProcedure` for direct context-managed work.
