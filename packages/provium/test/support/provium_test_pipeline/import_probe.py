"""Record imports of deliberately lazy fixture implementation modules."""

from __future__ import annotations

import os
from pathlib import Path


def record_implementation_import(module: str) -> None:
    """Append an implementation name when an import sentinel is configured."""
    sentinel = os.environ.get("PROVIUM_TEST_IMPORT_SENTINEL")
    if sentinel is not None:
        with Path(sentinel).open("a", encoding="utf-8") as stream:
            stream.write(f"{module}\n")
