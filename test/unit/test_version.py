from importlib.metadata import version

from provium import __version__


def test_version_matches_installed_package_metadata() -> None:
    assert __version__ == version("provium")
