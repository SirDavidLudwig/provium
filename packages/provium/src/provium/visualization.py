"""Generate and render visual representations of artifact provenance."""

from __future__ import annotations

import shutil
import subprocess
from html import escape
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from .provenance import ArtifactLineage


class BackendUnavailableError(RuntimeError):
    """Raised when a requested visualization backend is not installed."""


class UnsupportedFormatError(ValueError):
    """Raised when a visualization backend cannot produce a format."""


def _require_lineage(lineage: ArtifactLineage) -> None:
    if not isinstance(lineage, ArtifactLineage):
        raise TypeError("lineage must be an ArtifactLineage")


def _graphviz_graph(
    lineage: ArtifactLineage,
    *,
    format: str,
    show_artifact_identities: bool = False,
    show_procedure_versions: bool = False,
    show_execution_identities: bool = False,
) -> Any:
    _require_lineage(lineage)
    try:
        from graphviz import FORMATS, Source
    except ImportError as error:
        raise BackendUnavailableError(
            "Graphviz rendering requires the 'graphviz' Python package and "
            "Graphviz executable"
        ) from error
    if format not in FORMATS:
        supported = ", ".join(sorted(FORMATS))
        raise UnsupportedFormatError(
            f"Graphviz does not support format {format!r}; supported formats: "
            f"{supported}"
        )
    source = lineage_to_dot(
        lineage,
        show_artifact_identities=show_artifact_identities,
        show_procedure_versions=show_procedure_versions,
        show_execution_identities=show_execution_identities,
    )
    return Source(source, format=format)


def _dot_primary(value: str) -> str:
    return f'<FONT COLOR="#0F172A"><B>{escape(value, quote=True)}</B></FONT>'


def _dot_field(label: str, value: str, *, color: str) -> str:
    return (
        f'<FONT COLOR="{color}"><B>{label}</B></FONT> '
        f'<FONT FACE="monospace" COLOR="#475569">'
        f"{escape(value, quote=True)}</FONT>"
    )


def _mermaid_primary(value: str) -> str:
    return (
        "<span style='color:#0F172A;font-weight:700'>"
        f"{escape(value, quote=True)}</span>"
    )


def _mermaid_field(label: str, value: str, *, color: str) -> str:
    return (
        f"<span style='color:{color};font-weight:700'>{label}</span> "
        "<span style='font-family:monospace;color:#475569'>"
        f"{escape(value, quote=True)}</span>"
    )


def lineage_to_dot(
    lineage: ArtifactLineage,
    *,
    show_artifact_identities: bool = False,
    show_procedure_versions: bool = False,
    show_execution_identities: bool = False,
) -> str:
    """Return deterministic DOT source without requiring Graphviz."""
    _require_lineage(lineage)
    artifact_nodes = {
        identity: f"artifact_{index}"
        for index, identity in enumerate(sorted(lineage.artifacts))
    }
    execution_nodes = {
        identity: f"execution_{index}"
        for index, identity in enumerate(sorted(lineage.executions))
    }
    lines = [
        "digraph provium_lineage {",
        "    rankdir=LR;",
        '    node [shape="box", fontname="Helvetica"];',
        '    edge [color="#CBD5E1", penwidth="1.5", arrowsize="0.7"];',
    ]
    for identity, node in artifact_nodes.items():
        reference = lineage.artifacts[identity].reference
        label_parts = [_dot_primary(reference.artifact_identifier)]
        if show_artifact_identities:
            label_parts.append(
                _dot_field("Identity:", reference.identity, color="#0284C7")
            )
        label = "<BR/>".join(label_parts)
        lines.append(
            f'    {node} [label=<{label}>, color="#38BDF8", '
            'fillcolor="#F8FAFC", fontcolor="#0F172A", '
            'penwidth="1.5", style="filled"];'
        )
    for identity, node in execution_nodes.items():
        execution = lineage.executions[identity]
        procedure = execution.procedure
        label_parts = [_dot_primary(procedure.name)]
        if show_procedure_versions:
            label_parts.append(
                _dot_field("Version:", procedure.version, color="#7C3AED")
            )
        if show_execution_identities:
            label_parts.append(
                _dot_field("Execution Identity:", identity, color="#64748B")
            )
        label = "<BR/>".join(label_parts)
        lines.append(
            f'    {node} [label=<{label}>, color="#A78BFA", '
            'fillcolor="#FAF5FF", fontcolor="#0F172A", '
            'penwidth="1.5", style="rounded,filled"];'
        )
        for reference in execution.inputs:
            lines.append(f"    {artifact_nodes[reference.identity]} -> {node};")
        for reference in execution.outputs:
            lines.append(f"    {node} -> {artifact_nodes[reference.identity]};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def lineage_to_mermaid(
    lineage: ArtifactLineage,
    *,
    show_artifact_identities: bool = False,
    show_procedure_versions: bool = False,
    show_execution_identities: bool = False,
) -> str:
    """Return a deterministic Mermaid flowchart for an artifact lineage."""
    _require_lineage(lineage)
    artifact_nodes = {
        identity: f"artifact_{index}"
        for index, identity in enumerate(sorted(lineage.artifacts))
    }
    execution_nodes = {
        identity: f"execution_{index}"
        for index, identity in enumerate(sorted(lineage.executions))
    }
    lines = [
        "flowchart LR",
        "    classDef artifact fill:#F8FAFC,stroke:#38BDF8,"
        "color:#0F172A,stroke-width:1.5px",
        "    classDef procedure fill:#FAF5FF,stroke:#A78BFA,"
        "color:#0F172A,stroke-width:1.5px",
        "    linkStyle default stroke:#CBD5E1,stroke-width:1.5px",
    ]
    for identity, node in artifact_nodes.items():
        reference = lineage.artifacts[identity].reference
        label_parts = [_mermaid_primary(reference.artifact_identifier)]
        if show_artifact_identities:
            label_parts.append(
                _mermaid_field("Identity:", reference.identity, color="#0284C7")
            )
        label = "<br/>".join(label_parts)
        lines.append(f'    {node}["{label}"]:::artifact')
    for identity, node in execution_nodes.items():
        procedure = lineage.executions[identity].procedure
        label_parts = [_mermaid_primary(procedure.name)]
        if show_procedure_versions:
            label_parts.append(
                _mermaid_field("Version:", procedure.version, color="#7C3AED")
            )
        if show_execution_identities:
            label_parts.append(
                _mermaid_field("Execution Identity:", identity, color="#64748B")
            )
        label = "<br/>".join(label_parts)
        lines.append(f'    {node}(["{label}"]):::procedure')
    for identity in sorted(lineage.executions):
        execution = lineage.executions[identity]
        execution_node = execution_nodes[identity]
        for reference in execution.inputs:
            lines.append(
                f"    {artifact_nodes[reference.identity]} --> {execution_node}"
            )
        for reference in execution.outputs:
            lines.append(
                f"    {execution_node} --> {artifact_nodes[reference.identity]}"
            )
    return "\n".join(lines) + "\n"


def _render_graphviz(
    lineage: ArtifactLineage,
    format: str,
    *,
    show_artifact_identities: bool = False,
    show_procedure_versions: bool = False,
    show_execution_identities: bool = False,
) -> bytes:
    graph = _graphviz_graph(
        lineage,
        format=format,
        show_artifact_identities=show_artifact_identities,
        show_procedure_versions=show_procedure_versions,
        show_execution_identities=show_execution_identities,
    )
    from graphviz.backend import ExecutableNotFound

    try:
        return graph.pipe()
    except ExecutableNotFound as error:
        raise BackendUnavailableError(
            "Graphviz rendering requires a Graphviz executable on PATH"
        ) from error


def _render_mermaid(
    lineage: ArtifactLineage,
    format: str,
    *,
    show_artifact_identities: bool = False,
    show_procedure_versions: bool = False,
    show_execution_identities: bool = False,
) -> bytes:
    supported = {"pdf", "png", "svg"}
    if format not in supported:
        choices = ", ".join(sorted(supported))
        raise UnsupportedFormatError(
            f"Mermaid does not support format {format!r}; supported formats: {choices}"
        )
    executable = shutil.which("mmdc")
    if executable is None:
        raise BackendUnavailableError(
            "Mermaid rendering requires the 'mmdc' executable on PATH"
        )
    source = lineage_to_mermaid(
        lineage,
        show_artifact_identities=show_artifact_identities,
        show_procedure_versions=show_procedure_versions,
        show_execution_identities=show_execution_identities,
    )
    with TemporaryDirectory(prefix="provium-mermaid-") as directory:
        output = Path(directory) / f"lineage.{format}"
        subprocess.run(
            [executable, "--input", "-", "--output", str(output)],
            input=source,
            check=True,
            text=True,
            capture_output=True,
        )
        return output.read_bytes()


def render_lineage(
    lineage: ArtifactLineage,
    *,
    format: str,
    backend: str = "auto",
    show_artifact_identities: bool = False,
    show_procedure_versions: bool = False,
    show_execution_identities: bool = False,
) -> bytes:
    """Render an artifact lineage with the selected optional backend."""
    _require_lineage(lineage)
    renderers = {
        "graphviz": _render_graphviz,
        "mermaid": _render_mermaid,
    }
    label_options = {
        name: enabled
        for name, enabled in {
            "show_artifact_identities": show_artifact_identities,
            "show_procedure_versions": show_procedure_versions,
            "show_execution_identities": show_execution_identities,
        }.items()
        if enabled
    }
    if backend != "auto":
        try:
            renderer = renderers[backend]
        except KeyError as error:
            raise ValueError(f"unknown visualization backend: {backend!r}") from error
        return renderer(lineage, format, **label_options)

    failures: list[Exception] = []
    for renderer in renderers.values():
        try:
            return renderer(lineage, format, **label_options)
        except (BackendUnavailableError, UnsupportedFormatError) as error:
            failures.append(error)
    details = "; ".join(str(error) for error in failures)
    raise RuntimeError(f"no visualization backend can render {format!r}: {details}")


__all__ = [
    "BackendUnavailableError",
    "UnsupportedFormatError",
    "lineage_to_dot",
    "lineage_to_mermaid",
    "render_lineage",
]
