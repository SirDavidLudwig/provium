from __future__ import annotations

import os
import subprocess
import sys

import pytest

from provium import Procedure


def test_infers_pydantic_serialization_and_preserves_nested_values() -> None:
    pydantic = pytest.importorskip("pydantic")

    class Nested(pydantic.BaseModel):
        enabled: bool

    class Settings(pydantic.BaseModel):
        name: str
        nested: Nested
        labels: list[str]

    config = Settings(name="sample", nested=Nested(enabled=True), labels=["a", "b"])

    snapshot = Procedure[Settings]("pydantic", "1").encode_config(config)

    assert snapshot is not None
    assert snapshot.codec_identifier == "pydantic-v2"
    assert snapshot.value == {
        "name": "sample",
        "nested": {"enabled": True},
        "labels": ["a", "b"],
    }


def run_isolated(code: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, (str(os.getcwd() + "/src"), environment.get("PYTHONPATH")))
    )
    return subprocess.run(
        [sys.executable, "-I", "-c", code],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def test_import_succeeds_when_pydantic_import_is_blocked() -> None:
    result = run_isolated(
        """
import sys
sys.path.insert(0, 'src')
class BlockPydantic:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'pydantic' or fullname.startswith('pydantic.'):
            raise ImportError('pydantic is unavailable')
        return None
sys.meta_path.insert(0, BlockPydantic())
import provium
assert provium.Procedure('example', '1').encode_config(None) is None
"""
    )

    assert result.returncode == 0, result.stderr


def test_normal_non_pydantic_use_does_not_import_pydantic() -> None:
    result = run_isolated(
        """
import sys
sys.path.insert(0, 'src')
import provium
assert 'pydantic' not in sys.modules
provium.Procedure('example', '1').encode_config(None)
assert 'pydantic' not in sys.modules
"""
    )

    assert result.returncode == 0, result.stderr
