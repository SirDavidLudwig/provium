from collections.abc import Callable
from pathlib import Path
from typing import get_type_hints

from provium import Artifact, ArtifactReader, ArtifactWriter


def test_artifact_metadata_retains_its_generic_reader_and_writer_types() -> None:
    reader_type, writer_type = Artifact.__type_params__
    annotations = get_type_hints(Artifact)

    assert reader_type.__bound__ is ArtifactReader
    assert writer_type.__bound__ is ArtifactWriter
    assert annotations["reader"] == type[reader_type]
    assert annotations["writer"] == type[writer_type]
    assert annotations["dump"] == Callable[[reader_type, Path], None] | None
    assert annotations["load"] == Callable[[Path, writer_type], None] | None
