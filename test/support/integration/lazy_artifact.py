from __future__ import annotations

from typing import TYPE_CHECKING

from provium import Artifact, ArtifactReader, ArtifactWriter

if TYPE_CHECKING:
    from .lazy_reader import LazyReader
    from .lazy_writer import LazyWriter
else:
    LazyReader = ArtifactReader
    LazyWriter = ArtifactWriter


class LazyArtifact(Artifact[LazyReader, LazyWriter]):
    @staticmethod
    def reader() -> type[LazyReader]:
        from .lazy_reader import LazyReader

        return LazyReader

    @staticmethod
    def writer() -> type[LazyWriter]:
        from .lazy_writer import LazyWriter

        return LazyWriter
