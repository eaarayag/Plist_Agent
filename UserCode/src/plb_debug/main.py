"""
Entry point for PLB Debug Tool.

Usage:
    python main.py --gui                                    # GUI mode
    python main.py --interactive                            # Interactive CLI mode
    python main.py --plist scan_foo.plist --search "inf*atpg*ph1" --mode 1  # Batch mode

Run `python main.py --help` for the full list of options.
"""

import os
import sys

# Add the project root to sys.path so all `libs.*` imports resolve correctly.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from libs.app_runner import AppRunner


def main() -> None:
    app = AppRunner()
    app.run()  # setup() → start() → shutdown()


if __name__ == "__main__":
    main()
