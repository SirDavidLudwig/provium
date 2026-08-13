"""Mermaid source generation and CLI-backed rendering."""

from __future__ import annotations

import subprocess
from html import escape
from pathlib import Path
from tempfile import TemporaryDirectory

from provium.provenance import ArtifactLineage


def lineage_to_mermaid(lineage: ArtifactLineage) -> str:
    """Return a deterministic Mermaid flowchart for an artifact lineage."""
    if not isinstance(lineage, ArtifactLineage):
        raise TypeError("lineage must be an ArtifactLineage")

    artifact_nodes = {
        identity: f"artifact_{index}"
        for index, identity in enumerate(sorted(lineage.artifacts))
    }
    execution_nodes = {
        identity: f"execution_{index}"
        for index, identity in enumerate(sorted(lineage.executions))
    }
    lines = ["flowchart LR"]
    for identity, node in artifact_nodes.items():
        reference = lineage.artifacts[identity].reference
        label = escape(
            f"{reference.artifact_identifier}<br/>{reference.identity}",
            quote=True,
        ).replace("&lt;br/&gt;", "<br/>")
        lines.append(f'    {node}["{label}"]')
    for identity, node in execution_nodes.items():
        procedure = lineage.executions[identity].procedure
        label = escape(
            f"{procedure.name} {procedure.version}<br/>{identity}",
            quote=True,
        ).replace("&lt;br/&gt;", "<br/>")
        lines.append(f'    {node}(["{label}"])')
    for identity in sorted(lineage.executions):
        execution = lineage.executions[identity]
        execution_node = execution_nodes[identity]
        for reference in execution.inputs:
            artifact_node = artifact_nodes[reference.identity]
            lines.append(f"    {artifact_node} --> {execution_node}")
        for reference in execution.outputs:
            artifact_node = artifact_nodes[reference.identity]
            lines.append(f"    {execution_node} --> {artifact_node}")
    return "\n".join(lines) + "\n"


def render_mermaid(lineage: ArtifactLineage, *, format: str = "png") -> bytes:
    """Render lineage with Mermaid CLI and return the resulting image bytes."""
    source = lineage_to_mermaid(lineage)
    with TemporaryDirectory(prefix="provium-mermaid-") as directory:
        output = Path(directory) / f"lineage.{format}"
        try:
            subprocess.run(
                ["mmdc", "--input", "-", "--output", str(output)],
                input=source,
                check=True,
                text=True,
                capture_output=True,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            raise RuntimeError(
                "Mermaid image rendering requires the mmdc executable"
            ) from error
        return output.read_bytes()


__all__ = ["lineage_to_mermaid", "render_mermaid"]
