from provium.cli import main


def test_main_succeeds() -> None:
    assert main() == 0
