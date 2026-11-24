"""Entry point: ``python -m ft891prog`` (or the built FT891Programmer.exe)."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ft891prog", description="Yaesu FT-891 settings and memory programmer")
    parser.add_argument("--simulate", action="store_true",
                        help="preselect the built-in radio simulator instead of a serial port")
    args = parser.parse_args(argv)

    from .gui.app import run

    run(simulate=args.simulate)
    return 0


if __name__ == "__main__":
    sys.exit(main())
