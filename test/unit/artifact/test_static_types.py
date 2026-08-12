from __future__ import annotations

from typing import assert_type

from provium import Artifact, ArtifactReader, ArtifactWriter


class IntegerReader(ArtifactReader):
    pass


class IntegerWriter(ArtifactWriter):
    pass


class Integer(Artifact[IntegerReader, IntegerWriter]):
    reader = IntegerReader
    writer = IntegerWriter


def static_type_contract() -> None:
    assert_type(Integer.open("input.pa"), IntegerReader)
    assert_type(Integer.create("output.pa"), IntegerWriter)
