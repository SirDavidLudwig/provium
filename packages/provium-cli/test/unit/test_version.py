from importlib.metadata import version

from provium_cli import __version__


def test_package_version_matches_distribution_metadata() -> None:
    assert __version__ == version("provium-cli")
