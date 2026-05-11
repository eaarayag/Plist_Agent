"""
Entry point for remote_connection_demo.

Usage:
    python main.py
"""

import os
import sys

# Add UserCode/ root to sys.path so `from utilities.ssh_client import ...` resolves.
# This file lives at: UserCode/src/remote_connection_demo/main.py
#   parent     → UserCode/src/remote_connection_demo/
#   parent×2   → UserCode/src/
#   parent×3   → UserCode/
_USERCODE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _USERCODE_ROOT not in sys.path:
    sys.path.insert(0, _USERCODE_ROOT)

# Also add the project directory so `from libs.app_runner import AppRunner` resolves.
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from libs.app_runner import AppRunner


def main() -> None:
    app = AppRunner()
    app.run()  # setup() → start() → shutdown()


if __name__ == "__main__":
    main()

