"""Tests for provenance graph source generation and rendering."""

from __future__ import annotations

import sys
from types import ModuleType

import pytest

from provium import (
    ArtifactLineage,
    ArtifactRecord,
    ArtifactReference,
    ProcedureExecutionRecord,
    ProcedureRecord,
    lineage_to_dot,
    lineage_to_mermaid,
    render_lineage,
)


def lineage() -> ArtifactLineage:
    source = ArtifactReference("source-id", 'example.source<&"')
    result = ArtifactReference("result-id", "example.result")
    first = ProcedureExecutionRecord(
        "execution-1",
        ProcedureRecord('create<&"', "1.0"),
        outputs=(source,),
    )
    second = ProcedureExecutionRecord(
        "execution-2",
        ProcedureRecord("transform", "2.0"),
        inputs=(source,),
        outputs=(result,),
    )
    return ArtifactLineage(
        {
            source.identity: ArtifactRecord(source, "digest-1", first.identity),
            result.identity: ArtifactRecord(result, "digest-2", second.identity),
        },
        {first.identity: first, second.identity: second},
    )


def test_source_generators_hide_hashes_by_default() -> None:
    value = lineage()

    dot = lineage_to_dot(value)
    mermaid = lineage_to_mermaid(value)

    assert dot == lineage_to_dot(value)
    assert mermaid == lineage_to_mermaid(value)
    assert "artifact_1 -> execution_1" in dot
    assert "execution_1 -> artifact_0" in dot
    assert "artifact_1 --> execution_1" in mermaid
    assert "execution_1 --> artifact_0" in mermaid
    for source in (dot, mermaid):
        assert "example.source&lt;&amp;&quot;" in source
        assert "Artifact Identifier:" not in source
        assert "Procedure:" not in source
        assert "create&lt;&amp;&quot;" in source
        assert "source-id" not in source
        assert "execution-1" not in source
        assert "1.0" not in source


def test_source_generators_use_modern_semantic_text_palettes() -> None:
    value = lineage()

    options = {
        "show_artifact_identities": True,
        "show_procedure_versions": True,
        "show_execution_identities": True,
    }

    dot = lineage_to_dot(value, **options)
    assert 'color="#38BDF8"' in dot
    assert 'fillcolor="#F8FAFC"' in dot
    assert 'color="#A78BFA"' in dot
    assert 'fillcolor="#FAF5FF"' in dot
    assert '<FONT COLOR="#0284C7"><B>Identity:</B></FONT>' in dot
    assert '<FONT COLOR="#7C3AED"><B>Version:</B></FONT>' in dot
    assert 'style="filled"' in dot
    assert 'style="rounded,filled"' in dot
    assert '<FONT COLOR="#64748B"><B>Execution Identity:</B></FONT>' in dot
    assert 'FACE="monospace" COLOR="#475569"' in dot

    mermaid = lineage_to_mermaid(value, **options)
    assert "fill:#F8FAFC,stroke:#38BDF8,color:#0F172A" in mermaid
    assert "fill:#FAF5FF,stroke:#A78BFA,color:#0F172A" in mermaid
    assert "color:#0284C7;font-weight:700" in mermaid
    assert "color:#7C3AED;font-weight:700" in mermaid
    assert "color:#64748B;font-weight:700" in mermaid
    assert "font-family:monospace;color:#475569" in mermaid
    assert "stroke:#CBD5E1,stroke-width:1.5px" in mermaid


def test_source_generators_can_show_each_hash_kind_independently() -> None:
    value = lineage()

    for generate in (lineage_to_dot, lineage_to_mermaid):
        artifacts = generate(value, show_artifact_identities=True)
        versions = generate(value, show_procedure_versions=True)
        executions = generate(value, show_execution_identities=True)

        assert "Identity:" in artifacts
        assert "source-id" in artifacts
        assert "Version:" not in artifacts
        assert "Execution Identity:" not in artifacts
        assert "Identity:" not in versions
        assert "Version:" in versions
        assert "1.0" in versions
        assert "Execution Identity:" not in versions
        assert "Artifact Identity:" not in executions
        assert "Version:" not in executions
        assert "Execution Identity:" in executions
        assert "execution-1" in executions


def test_source_generators_reject_non_lineage_values() -> None:
    with pytest.raises(TypeError, match="ArtifactLineage"):
        lineage_to_dot(object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="ArtifactLineage"):
        lineage_to_mermaid(object())  # type: ignore[arg-type]


def test_render_auto_prefers_graphviz(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "provium.visualization._render_graphviz",
        lambda value, format: calls.append(("graphviz", format)) or b"graphviz",
    )
    monkeypatch.setattr(
        "provium.visualization._render_mermaid",
        lambda value, format: calls.append(("mermaid", format)) or b"mermaid",
    )

    assert render_lineage(lineage(), format="custom") == b"graphviz"
    assert calls == [("graphviz", "custom")]


def test_render_auto_falls_back_only_for_unavailable_or_unsupported_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from provium.visualization import BackendUnavailableError, UnsupportedFormatError

    calls: list[str] = []

    def unavailable(value: ArtifactLineage, format: str) -> bytes:
        calls.append("graphviz")
        raise BackendUnavailableError("graphviz unavailable")

    monkeypatch.setattr("provium.visualization._render_graphviz", unavailable)
    monkeypatch.setattr(
        "provium.visualization._render_mermaid",
        lambda value, format: calls.append("mermaid") or b"fallback",
    )
    assert render_lineage(lineage(), format="png") == b"fallback"
    assert calls == ["graphviz", "mermaid"]

    def unsupported(value: ArtifactLineage, format: str) -> bytes:
        raise UnsupportedFormatError("not supported")

    monkeypatch.setattr("provium.visualization._render_graphviz", unsupported)
    assert render_lineage(lineage(), format="new-format") == b"fallback"


def test_explicit_backend_is_strict_and_execution_errors_are_not_masked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from provium.visualization import BackendUnavailableError

    def unavailable(value: ArtifactLineage, format: str) -> bytes:
        raise BackendUnavailableError("graphviz unavailable")

    monkeypatch.setattr("provium.visualization._render_graphviz", unavailable)
    with pytest.raises(BackendUnavailableError, match="graphviz unavailable"):
        render_lineage(lineage(), format="png", backend="graphviz")

    def broken(value: ArtifactLineage, format: str) -> bytes:
        raise RuntimeError("renderer crashed")

    monkeypatch.setattr("provium.visualization._render_graphviz", broken)
    with pytest.raises(RuntimeError, match="renderer crashed"):
        render_lineage(lineage(), format="png")


def test_render_rejects_unknown_backend() -> None:
    with pytest.raises(ValueError, match="unknown visualization backend"):
        render_lineage(lineage(), format="png", backend="unknown")


class FakeExecutableNotFound(RuntimeError):
    pass


def install_fake_graphviz(
    monkeypatch: pytest.MonkeyPatch,
    *,
    formats: set[str] = {"png"},
    result: bytes | Exception = b"rendered",
) -> None:
    graphviz = ModuleType("graphviz")
    backend = ModuleType("graphviz.backend")

    class Source:
        def __init__(self, source: str, *, format: str) -> None:
            self.source = source
            self.format = format

        def pipe(self) -> bytes:
            if isinstance(result, Exception):
                raise result
            return result

    graphviz.FORMATS = formats  # type: ignore[attr-defined]
    graphviz.Source = Source  # type: ignore[attr-defined]
    backend.ExecutableNotFound = FakeExecutableNotFound  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "graphviz", graphviz)
    monkeypatch.setitem(sys.modules, "graphviz.backend", backend)


def test_graphviz_adapter_is_lazy_and_owns_format_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from provium.visualization import BackendUnavailableError, UnsupportedFormatError

    monkeypatch.setitem(sys.modules, "graphviz", None)
    with pytest.raises(BackendUnavailableError, match="Python package"):
        render_lineage(lineage(), format="png", backend="graphviz")

    install_fake_graphviz(monkeypatch)
    with pytest.raises(UnsupportedFormatError, match="supported formats: png"):
        render_lineage(lineage(), format="webp", backend="graphviz")
    assert render_lineage(lineage(), format="png", backend="graphviz") == b"rendered"


def test_graphviz_missing_executable_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fake_graphviz(
        monkeypatch,
        result=FakeExecutableNotFound("missing dot"),
    )

    from provium.visualization import BackendUnavailableError

    with pytest.raises(BackendUnavailableError, match="executable on PATH"):
        render_lineage(lineage(), format="png", backend="graphviz")


def test_mermaid_adapter_validates_availability_and_renders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from provium.visualization import BackendUnavailableError, UnsupportedFormatError

    with pytest.raises(UnsupportedFormatError, match="supported formats"):
        render_lineage(lineage(), format="webp", backend="mermaid")

    monkeypatch.setattr("provium.visualization.shutil.which", lambda name: None)
    with pytest.raises(BackendUnavailableError, match="mmdc"):
        render_lineage(lineage(), format="png", backend="mermaid")

    monkeypatch.setattr("provium.visualization.shutil.which", lambda name: "/bin/mmdc")

    def run(command: list[str], **kwargs: object) -> None:
        assert command[:4] == ["/bin/mmdc", "--input", "-", "--output"]
        assert kwargs["input"] == lineage_to_mermaid(lineage())
        assert kwargs["check"] is True
        assert kwargs["text"] is True
        assert kwargs["capture_output"] is True
        from pathlib import Path

        Path(command[4]).write_bytes(b"mermaid-image")

    monkeypatch.setattr("provium.visualization.subprocess.run", run)
    assert (
        render_lineage(lineage(), format="svg", backend="mermaid") == b"mermaid-image"
    )


def test_auto_reports_when_no_backend_can_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from provium.visualization import BackendUnavailableError, UnsupportedFormatError

    def unavailable(value: ArtifactLineage, format: str) -> bytes:
        raise BackendUnavailableError("graphviz missing")

    def unsupported(value: ArtifactLineage, format: str) -> bytes:
        raise UnsupportedFormatError("mermaid unsupported")

    monkeypatch.setattr("provium.visualization._render_graphviz", unavailable)
    monkeypatch.setattr("provium.visualization._render_mermaid", unsupported)
    with pytest.raises(RuntimeError, match="graphviz missing; mermaid unsupported"):
        render_lineage(lineage(), format="custom")
