"""
AppRunner orchestrates the PLB Debug Tool application lifecycle:
    setup() → start() → shutdown()

Dispatch logic:
  --gui          : launch GUI (Tkinter)
  --interactive  : interactive CLI (Step 1..5 prompts)
  --plist <file> : non-interactive batch runner (agent/automation mode)
"""

import argparse
import getpass
import os
import sys

# ─── Patch tkinter.messagebox BEFORE importing any project module ─────────────
import tkinter as _tk
from tkinter import messagebox as _msgbox

_msgbox.showwarning = lambda title, msg: print(f"\n[WARNING] {title}\n  {msg}")
_msgbox.showerror   = lambda title, msg: print(f"\n[ERROR]   {title}\n  {msg}")
_msgbox.showinfo    = lambda title, msg: print(f"\n[INFO]    {title}\n  {msg}")
# ──────────────────────────────────────────────────────────────────────────────

from libs.cli_app import CLIApp, resolve_plist_path, run as run_interactive
from libs.UsageLog import append_usage_log


# ─── Argument parsing ─────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="plb_debug",
        description="PLB Debug Tool — GUI, interactive CLI, or non-interactive batch runner.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # GUI mode
  python main.py --gui

  # Interactive CLI mode
  python main.py --interactive

  # Non-interactive (batch) mode — single search
  python main.py --plist scan_foo.plist --search "inf*atpg*ph1" --mode 1

  # Non-interactive — IO-equivalent search with custom suffix
  python main.py --plist scan_foo.plist --search "scn_c_inf_x_begin_sEs_edt_IEvinfra1_atpg_list" --mode 2 --suffix mytest

  # Non-interactive — two accumulated searches, no PreBurstPList
  python main.py --plist scan_foo.plist \\
      --search "inf*ph1" --mode 1 \\
      --search "clk*reset" --mode 1 \\
      --no-preburst
        """,
    )

    mode_group = p.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--gui",
        action="store_true",
        default=False,
        help="Launch the graphical user interface.",
    )
    mode_group.add_argument(
        "--interactive", "-i",
        action="store_true",
        default=False,
        help="Run in interactive CLI mode (step-by-step prompts).",
    )

    p.add_argument(
        "--plist", "-p",
        default=None,
        metavar="PATH",
        help="Path to the input .plist file (local, Windows absolute, or Unix-style network path).",
    )
    p.add_argument(
        "--search", "-s",
        action="append",
        dest="searches",
        default=[],
        metavar="TERM",
        help=(
            "Search term. Repeat for multiple searches. "
            "Each --search must be paired with a --mode that follows it."
        ),
    )
    p.add_argument(
        "--mode", "-m",
        action="append",
        dest="modes",
        default=[],
        choices=["1", "2"],
        metavar="1|2",
        help=(
            "Search mode for the preceding --search: "
            "1 = regex/wildcard, 2 = IO equivalent IE. "
            "Defaults to 1 for every search that has no explicit mode."
        ),
    )
    p.add_argument(
        "--no-preburst",
        action="store_true",
        default=False,
        help="Exclude PreBurstPList entries from output (default: included).",
    )
    p.add_argument(
        "--suffix",
        default="debug",
        metavar="SUFFIX",
        help="Custom suffix appended to the output file name (default: 'debug').",
    )
    p.add_argument(
        "--output", "-o",
        default=None,
        metavar="PATH",
        help=(
            "Output .plist file path. "
            "Defaults to <input_stem>_<suffix>.plist in the current directory."
        ),
    )
    return p


# ─── Batch runner ─────────────────────────────────────────────────────────────

def run_batch(
    plist_path: str,
    searches: list[tuple[str, str]],
    include_preburst: bool = True,
    suffix: str = "debug",
    output_path: str | None = None,
) -> int:
    """
    Execute the PLB Debug pipeline non-interactively.

    Parameters
    ----------
    plist_path      : resolved absolute path to the input .plist file
    searches        : list of (search_term, mode) tuples
                       mode "1" → regex/wildcard, "2" → IO equivalent IE
    include_preburst: whether to include PreBurstPList entries
    suffix          : output filename suffix
    output_path     : explicit output path; auto-derived when None

    Returns 0 on success, 1 on failure.
    """
    app = CLIApp()

    # ── Load file ────────────────────────────────────────────────────────────
    print(f"\n[1/4] Loading plist: {plist_path}")
    app.load_file(plist_path)

    # ── Search + extract loop ────────────────────────────────────────────────
    print(f"\n[2/4] Running {len(searches)} search(es) …")
    all_extracted_lines: list[str] = []

    for idx, (term, mode) in enumerate(searches, 1):
        print(f"\n  Search {idx}/{len(searches)}: mode={mode}  term={term!r}")

        # Reset viewer and match list for each search pass
        app.Plist_file_viewer_text_area.delete("1.0")
        app.Plist_file_viewer_text_area.insert("1.0", app.content)
        app.Selected_PList_extract_text_area.delete("1.0")
        app.matches = []
        app.current_index = 0

        if mode == "1":
            app.search_filter_user_input_text.set(term)
            app.Find_matches_search_main_global_PList()
            match_count = len(app.matches)
            print(f"    → {match_count} match(es) found.")
            if match_count == 0:
                print("    [WARN] No matches — skipping extraction for this search.")
                continue
            app.Extract_selected_matches()
        else:  # mode == "2"
            app.search_filter_user_input_text_tab2.set(term)
            app.Get_IO_Plist()
            match_count = len(app.matches)
            print(f"    → {match_count} match(es) found.")
            if match_count == 0:
                print("    [WARN] No matches — skipping extraction for this search.")
                continue
            app.Extract_selected_matches_IO()

        new_lines = app.Selected_PList_extract_text_area.lines()
        print(f"    → {len(new_lines)} line(s) extracted.")
        all_extracted_lines.extend(new_lines)

    if not all_extracted_lines:
        print("\n[ERROR] No lines were extracted across all searches. Aborting.")
        return 1

    # Consolidate all extracted lines back into the text area for generation
    app.Selected_PList_extract_text_area.delete("1.0")
    app.Selected_PList_extract_text_area.insert("1.0", "\n".join(all_extracted_lines))

    # ── Options ──────────────────────────────────────────────────────────────
    print(f"\n[3/4] Options:")
    print(f"  include_preburst = {include_preburst}")
    print(f"  suffix           = {suffix!r}")

    app.include_preburst.set(include_preburst)
    if suffix and suffix != "debug":
        app.use_debug_default.set(False)
        app.custom_name_plb.set(suffix)
    else:
        app.use_debug_default.set(True)
        app.custom_name_plb.set("")

    # ── Output path ──────────────────────────────────────────────────────────
    if not output_path:
        stem = os.path.splitext(os.path.basename(plist_path))[0]
        output_path = os.path.join(".", f"{stem}_{suffix}.plist")

    app.output_file_path = output_path

    # ── Generate ─────────────────────────────────────────────────────────────
    print(f"\n[4/4] Generating output …")
    ok = app.generate()

    if not ok:
        print("\n[ERROR] Generation failed. See messages above.")
        return 1

    # ── Usage log ────────────────────────────────────────────────────────────
    try:
        search_terms_str = " | ".join(t for t, _ in searches)
        append_usage_log(
            username    = getpass.getuser(),
            plb_name    = os.path.basename(output_path),
            search_text = search_terms_str,
            mtpl_file   = os.path.basename(plist_path),
        )
    except Exception:
        pass

    abs_out = os.path.abspath(output_path)
    print(f"\n  Done! Output saved to:\n  {abs_out}\n")
    return 0


# ─── AppRunner ────────────────────────────────────────────────────────────────

class AppRunner:
    """
    Lifecycle orchestrator for PLB Debug Tool.

    Dispatch (determined from sys.argv):
      --gui         → launch Tkinter GUI
      --interactive → interactive step-by-step CLI
      (default)     → non-interactive batch runner (requires --plist)
    """

    def __init__(self) -> None:
        self._args = None
        self._exit_code = 0

    def setup(self) -> None:
        """Parse command-line arguments."""
        parser = _build_parser()
        self._args = parser.parse_args()

    def start(self) -> None:
        """Dispatch to the appropriate mode."""
        args = self._args

        if args.gui:
            self._launch_gui()

        elif args.interactive:
            run_interactive()

        else:
            # Batch / non-interactive mode — requires --plist
            if not args.plist:
                print(
                    "[ERROR] Batch mode requires --plist. "
                    "Use --gui for GUI mode or --interactive for CLI prompts."
                )
                self._exit_code = 1
                return

            resolved = resolve_plist_path(args.plist)
            if not resolved:
                print(
                    f"[ERROR] PList file not found: {args.plist!r}\n"
                    "Accepted formats: local path, Windows absolute path, Unix-style network path."
                )
                self._exit_code = 1
                return

            # Pair searches with modes (pad with "1" if fewer modes than searches)
            searches_raw = args.searches
            modes_raw    = args.modes

            if not searches_raw:
                print("[ERROR] Batch mode requires at least one --search term.")
                self._exit_code = 1
                return

            modes_padded = list(modes_raw) + ["1"] * (len(searches_raw) - len(modes_raw))
            searches = list(zip(searches_raw, modes_padded))

            self._exit_code = run_batch(
                plist_path      = resolved,
                searches        = searches,
                include_preburst= not args.no_preburst,
                suffix          = args.suffix,
                output_path     = args.output,
            )

    def shutdown(self) -> None:
        """Exit with the recorded exit code."""
        if self._exit_code != 0:
            sys.exit(self._exit_code)

    def run(self) -> None:
        """Execute the full application lifecycle."""
        self.setup()
        self.start()
        self.shutdown()

    # ── Private helpers ───────────────────────────────────────────────────────

    def _launch_gui(self) -> None:
        """Launch the Tkinter GUI application."""
        import tkinter as tk
        from libs.GUI.Main_GUI import PlistTool
        root = tk.Tk()
        PlistTool(root)
        root.mainloop()
