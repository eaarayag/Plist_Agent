"""
Entry point for <project_name>.

Usage:
    python main.py --arg1 <value> --arg2 <value>
"""

import argparse
from libs.app_runner import AppRunner


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="<project_name> application.")
    # TODO: define your CLI arguments here
    # parser.add_argument("--input", required=True, help="Path to input file")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    app = AppRunner(
        # TODO: pass parsed args to AppRunner
        # input_path=args.input,
    )
    app.run()  # setup() → start() → shutdown()


if __name__ == "__main__":
    main()
