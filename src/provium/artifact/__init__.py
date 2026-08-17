"""Artifact definitions, containers, catalogs, and I/O primitives."""

from .catalog import ArtifactCatalog, ArtifactRegistration
from .definition import Artifact, open_artifact
from .discovery import discover_catalogs, reset_discovery
from .header import ArtifactHeader, decode_header, encode_header
from .prefab import JsonArtifact, JsonArtifactReader, JsonArtifactWriter
from .reader import ArtifactReader
from .region import BodyRegion
from .transfer import dump_artifact, inspect_dump, load_artifact, verify_dump
from .writer import ArtifactWriter

__all__ = [
    "Artifact",
    "ArtifactCatalog",
    "ArtifactHeader",
    "ArtifactReader",
    "ArtifactRegistration",
    "ArtifactWriter",
    "BodyRegion",
    "JsonArtifact",
    "JsonArtifactReader",
    "JsonArtifactWriter",
    "decode_header",
    "discover_catalogs",
    "encode_header",
    "dump_artifact",
    "load_artifact",
    "inspect_dump",
    "open_artifact",
    "reset_discovery",
    "verify_dump",
]
