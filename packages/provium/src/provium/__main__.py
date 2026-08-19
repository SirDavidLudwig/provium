from __future__ import annotations

import importlib.util


def main() -> int:
    """Delegate module execution to the optional Provium CLI package."""
    if importlib.util.find_spec("provium_cli") is None:
        raise SystemExit(
            "The Provium CLI is not installed. Install it with: "
            "python3 -m pip install provium-cli"
        )

    from provium_cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
