from __future__ import annotations

from provium import ArtifactReader


class LazyReader(ArtifactReader):
    def read(self) -> bytes:
        return self.body.read()
