from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID


def run(
    *arguments: str,
    cwd: Path | None = None,
    environment: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=cwd,
        env={
            **os.environ,
            "PYTHONNOUSERSITE": "1",
            **({} if environment is None else environment),
        },
        check=check,
        capture_output=True,
        text=True,
    )


def test_installed_wheels_complete_external_plugin_workflow(
    tmp_path: Path,
) -> None:
    repository = Path(__file__).parents[4]
    distributions = tmp_path / "dist"
    distributions.mkdir()
    projects = (
        repository / "packages" / "provium",
        repository / "packages" / "provium-cli",
        Path(__file__).parent / "example_plugin",
        repository / "examples" / "provium-text-pipeline",
    )
    for project in projects:
        run(
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--outdir",
            str(distributions),
            str(project),
        )

    environment = tmp_path / "environment"
    run(sys.executable, "-m", "venv", "--system-site-packages", str(environment))
    python = environment / "bin" / "python"
    wheels = tuple(str(path) for path in sorted(distributions.glob("*.whl")))
    run(str(python), "-m", "pip", "install", "--no-deps", *wheels)

    imported_paths = run(
        str(python),
        "-c",
        (
            "import provium, provium_cli, provium_example_plugin, "
            "provium_text_pipeline; "
            "print(provium.__file__); print(provium_cli.__file__); "
            "print(provium_example_plugin.__file__); "
            "print(provium_text_pipeline.__file__)"
        ),
        cwd=tmp_path,
    ).stdout.splitlines()
    assert len(imported_paths) == 4
    assert all(Path(path).is_relative_to(environment) for path in imported_paths)

    version = run(str(python), "-m", "provium", "--version", cwd=tmp_path)
    assert version.stdout == "provium 0.5.0\nprovium-cli 0.5.0\n"
    listed = run(str(python), "-m", "provium", "procedure", "list", cwd=tmp_path)
    assert "smoke.SourceTextV1\tSource text" in listed.stdout
    assert "smoke.TransformTextV1\tTransform text" in listed.stdout
    assert "smoke.FailingTextV1\tFailing text" in listed.stdout
    assert "example.TokenizeTextV1\tTokenize text" in listed.stdout
    assert "example.AggregateWordCountsV1\tAggregate word counts" in listed.stdout

    sentinel = tmp_path / "imports.log"
    sentinel_environment = {"PROVIUM_TEST_IMPORT_SENTINEL": str(sentinel)}
    shown = run(
        str(python),
        "-m",
        "provium",
        "procedure",
        "show",
        "smoke.TransformTextV1",
        cwd=tmp_path,
        environment=sentinel_environment,
    )
    assert "provium execute smoke.TransformTextV1" in shown.stdout
    assert not sentinel.exists()
    resolved = run(
        str(python),
        "-m",
        "provium",
        "procedure",
        "show",
        "smoke.TransformTextV1",
        "--resolve",
        cwd=tmp_path,
        environment=sentinel_environment,
    )
    assert "Resolved: provium_example_plugin.procedures.TransformProcedure" in (
        resolved.stdout
    )
    assert sentinel.read_text(encoding="utf-8").splitlines() == [
        "procedures",
        "artifacts",
    ]

    def create_source(name: str, text: str) -> Path:
        configuration = tmp_path / f"{name}.json"
        destination = tmp_path / f"{name}.provium"
        configuration.write_text(json.dumps({"text": text}), encoding="utf-8")
        executed = run(
            str(python),
            "-m",
            "provium",
            "execute",
            "smoke.SourceTextV1",
            "--config",
            str(configuration),
            "--output",
            f"value={destination}",
            cwd=tmp_path,
        )
        assert str(UUID(executed.stdout.strip())) == executed.stdout.strip()
        return destination

    setup = create_source("setup", "S")
    required = create_source("required", "R")
    optional = create_source("optional", "O")
    repeated_first = create_source("repeated-first", "A")
    repeated_second = create_source("repeated-second", "B")
    json_configuration = tmp_path / "transform.json"
    yaml_configuration = tmp_path / "transform.yaml"
    json_configuration.write_text(
        json.dumps({"prefix": "<", "suffix": "overridden"}),
        encoding="utf-8",
    )
    yaml_configuration.write_text('suffix: ">"\n', encoding="utf-8")
    transformed = tmp_path / "transformed.provium"
    summary = tmp_path / "summary.provium"
    transformed_execution = run(
        str(python),
        "-m",
        "provium",
        "execute",
        "smoke.TransformTextV1",
        "--config",
        str(json_configuration),
        "--config",
        str(yaml_configuration),
        "--setup-input",
        f"setup={setup}",
        "--input",
        f"required={required}",
        "--input",
        f"optional={optional}",
        "--input",
        f"repeated={repeated_first}",
        "--input",
        f"repeated={repeated_second}",
        "--output",
        f"transformed={transformed}",
        "--output",
        f"summary={summary}",
        cwd=tmp_path,
    ).stdout.strip()
    assert str(UUID(transformed_execution)) == transformed_execution

    input_paths = [
        str(path)
        for path in (
            setup,
            required,
            optional,
            repeated_first,
            repeated_second,
        )
    ]
    verification_script = f"""
import hashlib
from provium import ArtifactReference, session
from provium_example_plugin.artifacts import TextArtifact

input_paths = {input_paths!r}
output_paths = {[str(transformed), str(summary)]!r}
expected_bodies = ["<SROAB>", "inputs=5;characters=7"]
input_references = []
for path in input_paths:
    with session():
        with TextArtifact.bind_read(path).open() as reader:
            input_references.append(
                ArtifactReference(reader.identity, reader.artifact_identifier)
            )
output_headers = []
for path, expected in zip(output_paths, expected_bodies, strict=True):
    with session():
        with TextArtifact.bind_read(path).open() as reader:
            body = reader.read_text()
            header = reader.metadata
    assert body == expected
    assert header.body_length == len(expected.encode())
    assert header.body_digest == hashlib.sha256(expected.encode()).hexdigest()
    output_headers.append(header)
assert output_headers[0].artifact_identity != output_headers[1].artifact_identity
assert output_headers[0].lineage == output_headers[1].lineage
execution = output_headers[0].lineage.executions[{transformed_execution!r}]
assert execution.inputs == tuple(input_references)
assert {{reference.identity for reference in execution.outputs}} == {{
    header.artifact_identity for header in output_headers
}}
"""
    run(str(python), "-c", verification_script, cwd=tmp_path)

    console = run(
        str(environment / "bin" / "provium"),
        "procedure",
        "list",
        cwd=tmp_path,
    )
    assert console.stdout == listed.stdout

    existing = tmp_path / "existing.provium"
    existing.write_bytes(b"original")
    paths_before_failure = set(tmp_path.iterdir())
    failed = run(
        str(python),
        "-m",
        "provium",
        "execute",
        "smoke.FailingTextV1",
        "--input",
        f"source={required}",
        "--output",
        f"result={existing}",
        cwd=tmp_path,
        check=False,
    )
    assert failed.returncode == 2
    assert failed.stdout == ""
    assert "deliberate installed-plugin failure" in failed.stderr
    assert existing.read_bytes() == b"original"
    assert set(tmp_path.iterdir()) == paths_before_failure

    raw_text = tmp_path / "example-input.provium"
    create_example_input = f"""
from provium import ImperativeProcedure
from provium_text_pipeline.artifacts import RawTextArtifact

output = RawTextArtifact.bind_write({str(raw_text)!r})
with ImperativeProcedure("example.SeedRawTextV1", "acceptance-test").execute(
    outputs={{"text": output}}
):
    with output.open() as writer:
        writer.write("Hello hello world and Provium")
"""
    run(str(python), "-c", create_example_input, cwd=tmp_path)
    tokenize_configuration = tmp_path / "tokenize.json"
    tokenize_configuration.write_text(
        json.dumps({"lowercase": True, "min_token_length": 4}),
        encoding="utf-8",
    )
    tokens = tmp_path / "example-tokens.provium"
    tokenize_execution = run(
        str(python),
        "-m",
        "provium",
        "execute",
        "example.TokenizeTextV1",
        "--config",
        str(tokenize_configuration),
        "--input",
        f"text={raw_text}",
        "--output",
        f"tokens={tokens}",
        cwd=tmp_path,
    ).stdout.strip()
    assert str(UUID(tokenize_execution)) == tokenize_execution

    aggregate_configuration = tmp_path / "aggregate.yaml"
    aggregate_configuration.write_text("top_n: 2\n", encoding="utf-8")
    counts = tmp_path / "example-counts.provium"
    aggregate_execution = run(
        str(python),
        "-m",
        "provium",
        "execute",
        "example.AggregateWordCountsV1",
        "--config",
        str(aggregate_configuration),
        "--input",
        f"token_lists={tokens}",
        "--output",
        f"counts={counts}",
        cwd=tmp_path,
    ).stdout.strip()
    assert str(UUID(aggregate_execution)) == aggregate_execution

    inspect_example_output = f"""
from provium import session
from provium_text_pipeline.artifacts import TokenListArtifact, WordStatsArtifact

with session():
    with WordStatsArtifact.bind_read({str(counts)!r}).open() as reader:
        assert reader.read() == {{"hello": 2, "provium": 1}}
        metadata = reader.metadata
with session():
    with TokenListArtifact.bind_read({str(tokens)!r}).open() as reader:
        token_identity = reader.identity
assert metadata.artifact_identifier == "example.WordStatsV1"
execution = metadata.lineage.executions[{aggregate_execution!r}]
assert execution.procedure.name == "example.AggregateWordCountsV1"
assert len(execution.inputs) == 1
assert execution.inputs[0].identity == token_identity
"""
    run(str(python), "-c", inspect_example_output, cwd=tmp_path)
