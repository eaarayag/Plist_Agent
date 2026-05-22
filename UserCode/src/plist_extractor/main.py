"""
Entry point for plist_extractor.

Usage — batch mode:
    python main.py \\
        --plist   <path/to/input.plist> \\
        --partition <partition> [<partition> ...] \\
        --output  <path/to/output.plist> \\
        [--content-type <type> [<type> ...]] \\
        [--approach  <sSs|sEs|...>] \\
        [--phase     <ph1|ph2|...>] \\
        [--power-domain <domain>] \\
        [--frequency    <f1|f2|...>] \\
        [--flow         <chk|srh|vmax|...>] \\
        [--full-content] \\
        [--skip <pattern> ...]

Usage — interactive mode:
    python main.py --interactive
"""

from libs.app_runner import AppRunner


def main() -> None:
    app = AppRunner()
    app.run()  # setup() → start() → shutdown()


if __name__ == "__main__":
    main()
