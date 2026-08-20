"""Record imports of installed plugin implementation modules."""

import os
from pathlib import Path


def record_import(module: str) -> None:
    sentinel = os.environ.get("PROVIUM_TEST_IMPORT_SENTINEL")
    if sentinel is not None:
        with Path(sentinel).open("a", encoding="utf-8") as stream:
            stream.write(f"{module}\n")
