"""
Entry point for three_set_dbg_plist_gen.

Usage
-----
    # Process all sSs/IO/5o2 PLBs found in the file:
    python main.py -i <input.plist>

    # Process only the PLBs listed in a .list file:
    python main.py -i <input.plist> -m selected -l <plb_names.list>

    # Process all sSs/IO/5o2 PLBs EXCEPT those listed in a .list file:
    python main.py -i <input.plist> -m exclude -l <exclude_names.list>

    # Specify output location:
    python main.py -i <input.plist> -o <output_prefix>
"""

import argparse
import sys

from libs.app_runner import AppRunner


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Three Set Debug Plist Generator - reads a .plist file and produces "
            "U3 (nor) / U4 (mid) / U5 (sou) variant copies of every selected "
            "debug PLB chain (PLB -> content plists -> hotreset plists)."
        )
    )

    parser.add_argument(
        "-i", "--input",
        required=True,
        metavar="FILE",
        help="Path to the input .plist file.",
    )
    parser.add_argument(
        "-m", "--mode",
        choices=["all", "selected", "exclude"],
        default="all",
        metavar="MODE",
        help=(
            "Processing mode.  "
            "  'all'      - process every sSs/IO/5o2 PLB found in the file (default).  "
            "  'selected' - process only the PLBs listed in --list.  "
            "  'exclude'  - process all sSs/IO/5o2 PLBs EXCEPT those listed in --list."
        ),
    )
    parser.add_argument(
        "-l", "--list",
        default=None,
        metavar="FILE",
        help=(
            "Path to a .list file with PLB names, one per line "
            "(lines starting with '#' are treated as comments).  "
            "Required when --mode=selected (names to include) or "
            "--mode=exclude (names to skip)."
        ),
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        metavar="PREFIX",
        help=(
            "Output file prefix or directory.  "
            "If a directory is given (or the path ends with '/' or '\\'), the output "
            "files are placed there with the input file stem + '_three_set' as the base "
            "name.  Defaults to the same directory as the input file."
        ),
    )

    args = parser.parse_args()

    if args.mode in ("selected", "exclude") and not args.list:
        parser.error("--list is required when --mode=selected or --mode=exclude")

    return args


def main() -> None:
    args = _parse_args()
    app  = AppRunner(args)
    app.run()


if __name__ == "__main__":
    main()
