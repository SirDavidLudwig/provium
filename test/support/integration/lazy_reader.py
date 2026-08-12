from __future__ import annotations

from provium import ArtifactReader


class LazyReader(ArtifactReader):
    def read_value(self) -> bytes:
        return self.body.read()
