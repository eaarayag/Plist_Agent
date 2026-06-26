"""
Entry point for plist_converter.

Usage:
    python main.py \\
        --plist  <path/to/input.plist> \\
        --plbs   <path/to/plb_names.txt> \\
        --mode   <default-to-chico|chico-to-default> \\
        --output <path/to/output.plist>
"""

import os
import sys

# sys.path setup.
#
# Python automatically inserts the script's directory (plist_converter/) at
# sys.path[0] when the script is launched — so plist_converter/libs/ already
# has the highest lookup priority.  We must NOT push anything in front of it.
#
# Strategy:
#   • _USERCODE_ROOT    — appended (low priority; for utilities/ etc.)
#   • _PLIST_EXTRACTOR_ROOT — appended AFTER _USERCODE_ROOT so that
#     plist_extractor/libs/Parser.py is found as a fallback when plist_converter
#     does `from libs.Parser import ...` and its own libs/ has no Parser.py.
#
# This file lives at: UserCode/src/plist_converter/main.py
#   parent     → UserCode/src/plist_converter/
#   parent×2   → UserCode/src/
#   parent×3   → UserCode/
_USERCODE_ROOT        = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PROJECT_ROOT         = os.path.dirname(os.path.abspath(__file__))
_PLIST_EXTRACTOR_ROOT = os.path.join(_USERCODE_ROOT, "src", "plist_extractor")

if _USERCODE_ROOT not in sys.path:
    sys.path.append(_USERCODE_ROOT)
if _PLIST_EXTRACTOR_ROOT not in sys.path:
    sys.path.append(_PLIST_EXTRACTOR_ROOT)
# _PROJECT_ROOT is already at sys.path[0] (auto-inserted by Python).

from libs.app_runner import AppRunner


def main() -> None:
    app = AppRunner()
    app.run()  # setup() → start() → shutdown()


if __name__ == "__main__":
    main()
