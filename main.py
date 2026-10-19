"""Solar Panel Performance Monitor — headless-safe entry point.

Usage:
    python main.py --version
    python main.py          # launches the GUI (Part 2+)
"""
from __future__ import annotations

import argparse
import sys

__version__ = "1.0.0-dev"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="main.py", description="Solar Panel Performance Monitor")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    args = parser.parse_args(argv)

    if args.version:
        print(f"Solar Panel Performance Monitor v{__version__}")
        return 0

    from app.gui import run_gui  # noqa: PLC0415
    return run_gui()


if __name__ == "__main__":
    sys.exit(main())