from importlib.resources import files


def test_package_declares_inline_typing_support() -> None:
    assert files("provium").joinpath("py.typed").is_file()
