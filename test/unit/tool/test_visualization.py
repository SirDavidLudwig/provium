from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from provium import (
    ArtifactLineage,
    ArtifactRecord,
    ArtifactReference,
    ProcedureExecutionRecord,
    ProcedureRecord,
)
from provium.tool.visualization import (
    lineage_to_dot,
    lineage_to_mermaid,
    render_lineage,
    render_mermaid,
)


def sample_lineage() -> ArtifactLineage:
    source = ArtifactReference("source-id", "example.SourceV1")
    result = ArtifactReference("result-id", "example.ResultV1")
    source_execution = ProcedureExecutionRecord(
        "source-execution",
        ProcedureRecord("source", "1"),
        outputs=(source,),
    )
    result_execution = ProcedureExecutionRecord(
        "result-execution",
        ProcedureRecord("transform", "2"),
        inputs=(source,),
        outputs=(result,),
    )
    source_lineage = ArtifactLineage.for_execution(
        source_execution,
        (ArtifactRecord(source, "source-digest", source_execution.identity),),
    )
    return ArtifactLineage.for_execution(
        result_execution,
        (ArtifactRecord(result, "result-digest", result_execution.identity),),
        (source_lineage,),
    )


def test_render_lineage_builds_and_pipes_graph_in_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, ...]] = []

    class Digraph:
        def __init__(self, *, name: str, format: str) -> None:
            calls.append(("init", name, format))

        def attr(self, **attributes: str) -> None:
            calls.append(("attr", attributes))

        def node(self, name: str, label: str, **attributes: str) -> None:
            calls.append(("node", name, label, attributes))

        def edge(self, tail: str, head: str) -> None:
            calls.append(("edge", tail, head))

        def pipe(self) -> bytes:
            calls.append(("pipe",))
            return b"image"

    monkeypatch.setitem(sys.modules, "graphviz", SimpleNamespace(Digraph=Digraph))

    assert render_lineage(sample_lineage(), format="svg") == b"image"
    assert ("init", "provium-lineage", "svg") in calls
    assert ("edge", "artifact_1", "execution_0") in calls
    assert ("edge", "execution_0", "artifact_0") in calls
    procedure_nodes = [call for call in calls if call[:2] == ("node", "execution_0")]
    assert len(procedure_nodes) == 1
    assert "<B>transform</B>" in procedure_nodes[0][2]
    assert "Version: 2" in procedure_nodes[0][2]
    assert 'CELLPADDING="1"' in procedure_nodes[0][2]
    assert procedure_nodes[0][2].count("<TR>") == 3
    assert procedure_nodes[0][3] == {
        "color": "#7C3AED",
        "fillcolor": "#F3E8FF",
        "shape": "box",
        "style": "rounded,filled",
    }
    assert calls[-1] == ("pipe",)


def test_render_lineage_rejects_an_invalid_lineage() -> None:
    with pytest.raises(TypeError, match="ArtifactLineage"):
        render_lineage(object())


def test_render_lineage_reports_missing_graphviz(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "graphviz", None)

    with pytest.raises(RuntimeError, match="graphviz"):
        render_lineage(sample_lineage())


def test_lineage_to_mermaid_returns_deterministic_flowchart_source() -> None:
    assert lineage_to_mermaid(sample_lineage()) == (
        "flowchart LR\n"
        '    artifact_0["example.ResultV1<br/>result-id"]\n'
        '    artifact_1["example.SourceV1<br/>source-id"]\n'
        '    execution_0(["transform 2<br/>result-execution"])\n'
        '    execution_1(["source 1<br/>source-execution"])\n'
        "    artifact_1 --> execution_0\n"
        "    execution_0 --> artifact_0\n"
        "    execution_1 --> artifact_1\n"
    )


def test_lineage_to_mermaid_escapes_label_text() -> None:
    reference = ArtifactReference('artifact<&"', 'example.<&"')
    execution = ProcedureExecutionRecord(
        'execution<&"',
        ProcedureRecord('produce<&"', '1<&"'),
        outputs=(reference,),
    )
    lineage = ArtifactLineage.for_execution(
        execution,
        (ArtifactRecord(reference, "digest", execution.identity),),
    )

    source = lineage_to_mermaid(lineage)

    assert "example.&lt;&amp;&quot;<br/>artifact&lt;&amp;&quot;" in source
    assert "produce&lt;&amp;&quot; 1&lt;&amp;&quot;" in source
    assert 'artifact<&"' not in source


def test_lineage_to_mermaid_rejects_an_invalid_lineage() -> None:
    with pytest.raises(TypeError, match="ArtifactLineage"):
        lineage_to_mermaid(object())


def test_lineage_to_dot_returns_graphviz_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Digraph:
        source = "digraph lineage {}\n"

        def __init__(self, *, name: str, format: str) -> None:
            pass

        def attr(self, **attributes: str) -> None:
            pass

        def node(self, name: str, label: str, **attributes: str) -> None:
            pass

        def edge(self, tail: str, head: str) -> None:
            pass

    monkeypatch.setitem(sys.modules, "graphviz", SimpleNamespace(Digraph=Digraph))

    assert lineage_to_dot(sample_lineage()) == "digraph lineage {}\n"


def test_render_mermaid_uses_stdin_and_returns_image_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, ...]] = []

    def run(command: list[str], **options: object) -> None:
        calls.append((command, options))
        Path(command[-1]).write_bytes(b"mermaid image")

    monkeypatch.setattr("provium.tool.visualization.mermaid.subprocess.run", run)

    assert render_mermaid(sample_lineage(), format="png") == b"mermaid image"
    command, options = calls[0]
    assert command[:3] == ["mmdc", "--input", "-"]
    assert command[-2:] != ["--output", "-"]
    assert options["input"] == lineage_to_mermaid(sample_lineage())
    assert options["check"] is True
    assert options["text"] is True


@pytest.mark.parametrize("error", [FileNotFoundError(), OSError("failed")])
def test_render_mermaid_reports_an_unavailable_cli(
    monkeypatch: pytest.MonkeyPatch,
    error: OSError,
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise error

    monkeypatch.setattr("provium.tool.visualization.mermaid.subprocess.run", fail)

    with pytest.raises(RuntimeError, match="mmdc"):
        render_mermaid(sample_lineage())
