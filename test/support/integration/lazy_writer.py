from __future__ import annotations

from provium import ArtifactWriter


class LazyWriter(ArtifactWriter):
    def write(self, value: bytes) -> int:
        return self.body.write(value)
