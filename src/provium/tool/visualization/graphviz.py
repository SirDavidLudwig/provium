"""Graphviz source generation and in-memory rendering."""

from __future__ import annotations

from html import escape
from typing import Any

from provium.provenance import ArtifactLineage


def _graphviz() -> Any:
    try:
        from graphviz import Digraph
    except ImportError as error:
        raise RuntimeError(
            "lineage visualization requires the optional graphviz package"
        ) from error
    return Digraph


def _graphviz_graph(lineage: ArtifactLineage, *, format: str) -> Any:
    if not isinstance(lineage, ArtifactLineage):
        raise TypeError("lineage must be an ArtifactLineage")

    graph = _graphviz()(name="provium-lineage", format=format)
    graph.attr(rankdir="LR", nodesep="0.45", ranksep="0.8")
    artifact_nodes = {
        identity: f"artifact_{index}"
        for index, identity in enumerate(sorted(lineage.artifacts))
    }
    execution_nodes = {
        identity: f"execution_{index}"
        for index, identity in enumerate(sorted(lineage.executions))
    }
    for identity, node in artifact_nodes.items():
        record = lineage.artifacts[identity]
        reference = record.reference
        label = (
            '<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="1">'
            f"<TR><TD><B>{escape(reference.artifact_identifier)}</B></TD></TR>"
            f'<TR><TD><FONT POINT-SIZE="9" COLOR="#6B7280">'
            f"{escape(identity)}</FONT></TD></TR></TABLE>>"
        )
        graph.node(
            node,
            label,
            color="#2563EB",
            fillcolor="#EFF6FF",
            shape="box",
            style="filled",
        )
    for identity, node in execution_nodes.items():
        execution = lineage.executions[identity]
        procedure = execution.procedure
        label = (
            '<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="1">'
            f"<TR><TD><B>{escape(procedure.name)}</B></TD></TR>"
            f'<TR><TD><FONT POINT-SIZE="11">Version: '
            f"{escape(procedure.version)}</FONT></TD></TR>"
            f'<TR><TD><FONT POINT-SIZE="9" COLOR="#6B7280">'
            f"{escape(identity)}</FONT></TD></TR></TABLE>>"
        )
        graph.node(
            node,
            label,
            color="#7C3AED",
            fillcolor="#F3E8FF",
            shape="box",
            style="rounded,filled",
        )
        for reference in execution.inputs:
            graph.edge(artifact_nodes[reference.identity], node)
        for reference in execution.outputs:
            graph.edge(node, artifact_nodes[reference.identity])
    return graph


def render_lineage(lineage: ArtifactLineage, *, format: str = "png") -> bytes:
    """Render a Graphviz lineage entirely in memory and return its image bytes."""
    graph = _graphviz_graph(lineage, format=format)
    return graph.pipe()


def lineage_to_dot(lineage: ArtifactLineage) -> str:
    """Return Graphviz DOT source for an artifact lineage."""
    graph = _graphviz_graph(lineage, format="dot")
    return graph.source


__all__ = ["lineage_to_dot", "render_lineage"]
