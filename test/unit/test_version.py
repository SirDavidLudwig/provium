from importlib.metadata import version

import provium


def test_package_version_matches_project_metadata() -> None:
    assert provium.__version__ == version("provium")
