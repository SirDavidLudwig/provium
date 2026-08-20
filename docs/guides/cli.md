# Command-line tools

The command-line interface is included with `provium`. Both entry points use the
same plugin-discovered command catalog:

```bash
provium --version
python -m provium --version
```

## Discover procedures

List lightweight definitions without importing procedure implementations:

```bash
provium procedure list
```

Show a definition, its configuration schema, typed ports, cardinalities, and a
generated invocation synopsis:

```bash
provium procedure show example.DetectV1
```

Add `--resolve` to import and fully validate the implementation and every
artifact class referenced by its contract:

```bash
provium procedure show example.DetectV1 --resolve
```

## Execute a procedure

Bindings use `FIELD=PATH`. Repeat `--input` for a repeated field and repeat
`--config` to apply JSON or YAML layers in order (later values override earlier
ones).

```bash
provium execute example.DetectV1 \
  --config defaults.yaml \
  --config production.json \
  --setup-input model=model.pa \
  --input image=image.pa \
  --input references=reference-1.pa \
  --input references=reference-2.pa \
  --output detections=detections.pa
```

Optional inputs and outputs may be omitted. Unknown fields, bad cardinality,
invalid configuration, resolution failures, and processing failures are printed
to standard error and return exit status 2. Successful execution prints its
provenance execution identity and returns 0.

Run `provium --help`, `provium procedure --help`, or `provium execute --help`
for the installed command surface.
