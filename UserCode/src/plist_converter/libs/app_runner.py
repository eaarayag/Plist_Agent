"""
app_runner.py — AppRunner orchestrates the plist_converter application lifecycle.

Lifecycle
---------
    AppRunner.run()
        └── setup()    ← argparse
        └── start()    ← load PLB names → Parser → Extractor → Transformer → Generator
        └── shutdown() ← sys.exit(exit_code)

Modes
-----
    default-to-chico : collect blocks as-is (source is already chico-style)
    chico-to-default : collect blocks then split chico content blocks into
                       separate hotreset + content; strip PLB glue entries
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from src.plist_extractor.libs.Parser    import PlistParser, PlistEntry
from libs.Extractor    import PlistConverterExtractor, MODE_DEFAULT_TO_CHICO, MODE_CHICO_TO_DEFAULT
from libs.Transformer  import PlistTransformer
from libs.Generator    import PlistConverterGenerator, _is_hotreset, _is_plb


class AppRunner:
    def __init__(self) -> None:
        self._args:      argparse.Namespace | None = None
        self._exit_code: int = 0

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def setup(self) -> None:
        self._args = self._build_parser().parse_args()

    def start(self) -> None:
        assert self._args is not None
        args = self._args

        t0 = time.perf_counter()

        # ── Step 1: Load source plist ──────────────────────────────────────────
        print(f"\n[1/5] Loading source plist: {args.plist}")
        try:
            plist_file = PlistParser.parse(args.plist)
        except FileNotFoundError as exc:
            print(f"  ERROR: {exc}", file=sys.stderr)
            self._exit_code = 1
            return
        print(f"  Blocks found: {len(plist_file.blocks)}")

        # ── Step 2: Load PLB names from file ──────────────────────────────────
        print(f"\n[2/5] Reading PLB names from: {args.plbs}")
        plb_names = _load_plb_names(args.plbs)
        if plb_names is None:
            self._exit_code = 1
            return
        if not plb_names:
            print("  ERROR: PLB names file is empty (no names after stripping blanks/comments).",
                  file=sys.stderr)
            self._exit_code = 1
            return
        print(f"  PLB name(s) to process ({len(plb_names)}): {', '.join(plb_names)}")
        print(f"  Conversion mode: {args.mode}")

        # ── Step 3: Extract blocks ─────────────────────────────────────────────
        print(f"\n[3/5] Extracting blocks...")
        extractor = PlistConverterExtractor(plist_file, plb_names, args.mode)
        blocks = extractor.extract()

        if not blocks:
            print("  WARNING: No blocks found — output file will not be created.",
                  file=sys.stderr)
            self._exit_code = 1
            return

        _print_counts(blocks, "  Extracted")

        # ── Step 4: Transform blocks ───────────────────────────────────────────
        print(f"\n[4/5] Transforming blocks ({args.mode})...")
        transformer = PlistTransformer()
        if args.mode == MODE_CHICO_TO_DEFAULT:
            plb_blocks     = [b for b in blocks if _is_plb(b)]
            content_blocks = [b for b in blocks if not _is_plb(b) and not _is_hotreset(b)]
            blocks = transformer.chico_to_default(plb_blocks, content_blocks)
        else:  # default-to-chico
            plb_blocks      = [b for b in blocks if _is_plb(b)]
            hotreset_blocks = [b for b in blocks if _is_hotreset(b)]
            content_blocks  = [b for b in blocks if not _is_plb(b) and not _is_hotreset(b)]
            gid_clear_io, gid_clear_ie = _resolve_gid_clear(args, plist_file)
            blocks = transformer.default_to_chico(
                plb_blocks, content_blocks, hotreset_blocks, gid_clear_io, gid_clear_ie
            )
        _print_counts(blocks, "  Result")

        # ── Step 5: Write output ───────────────────────────────────────────────
        print(f"\n[5/5] Writing output: {args.output}")
        generator = PlistConverterGenerator()
        try:
            generator.write(blocks, args.output)
        except OSError:
            self._exit_code = 1
            return

        elapsed = time.perf_counter() - t0
        print(f"\n  Execution time: {elapsed:.2f}s")

    def shutdown(self) -> None:
        sys.exit(self._exit_code)

    def run(self) -> None:
        self.setup()
        self.start()
        self.shutdown()

    # ── Argparse ──────────────────────────────────────────────────────────────

    @staticmethod
    def _build_parser() -> argparse.ArgumentParser:
        p = argparse.ArgumentParser(
            prog="plist_converter",
            description=(
                "Convert .plist blocks between default (standard) and Chico structures.\n\n"
                "Modes:\n"
                "  default-to-chico  Merge hotreset into content; add PLB glue header/body\n"
                "  chico-to-default  Split merged content back into hotreset + content blocks\n"
            ),
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

        p.add_argument(
            "--plist",
            metavar="PATH",
            required=True,
            help="Input .plist file to read blocks from.",
        )
        p.add_argument(
            "--plbs",
            metavar="FILE",
            required=True,
            help=(
                "Text file containing PLB/main-plist names to process, "
                "one name per line.  Blank lines and lines starting with '#' are ignored."
            ),
        )
        p.add_argument(
            "--mode",
            choices=[MODE_DEFAULT_TO_CHICO, MODE_CHICO_TO_DEFAULT],
            required=True,
            help="Conversion direction.",
        )
        p.add_argument(
            "--output",
            metavar="PATH",
            required=True,
            help="Output .plist file path.",
        )
        p.add_argument(
            "--gid-clear",
            metavar="FILE",
            default=None,
            help=(
                "(default-to-chico only) Path to a text file with one or two gid_clear "
                "pattern names (one per line, '#' comments ignored).  The tool detects "
                "IO/sSs (5o2) vs IE/sEs (5o1) from the pattern name automatically. "
                "If omitted, the source plist is searched; if still not found, typed "
                "placeholders are written: '<gid_clear_pattern_IO>' and "
                "'<gid_clear_pattern_IE>'."
            ),
        )

        return p


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _load_plb_names(file_path: str) -> list[str] | None:
    """
    Read PLB names from *file_path*.  Returns a list of non-blank, non-comment
    lines, or None if the file cannot be read.
    """
    path = Path(file_path)
    if not path.is_file():
        print(f"  ERROR: PLB names file not found: {file_path}", file=sys.stderr)
        return None

    names: list[str] = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = raw.strip()
        if stripped and not stripped.startswith("#"):
            names.append(stripped)
    return names


def _print_counts(blocks: list, label: str = "") -> None:
    """Print hotreset / content / PLB / total counts for *blocks*."""
    plb_count      = sum(1 for b in blocks if _is_plb(b))
    hotreset_count = sum(1 for b in blocks if _is_hotreset(b))
    content_count  = len(blocks) - plb_count - hotreset_count
    prefix = f"{label} — " if label else ""
    print(f"  {prefix}Hotreset : {hotreset_count}")
    print(f"  {prefix}Content  : {content_count}")
    print(f"  {prefix}PLB(s)   : {plb_count}")
    print(f"  {prefix}Total    : {len(blocks)}")


def _resolve_gid_clear(
    args: argparse.Namespace,
    plist_file,
) -> tuple[PlistEntry, PlistEntry]:
    """
    Resolve gid_clear PlistEntry for IO (sSs/5o2) and IE (sEs/5o1) content blocks.

    Priority:
      1. --gid-clear FILE provided: read pattern names, classify by '5o2'/'5o1' in name.
         If only one name is given without a clear marker, use it for both types.
      2. Search the source plist_file for gid_clear patterns classified by '5o2'/'5o1'.
      3. Neither found: write typed placeholders so the user can fill them in.
    """
    _GID_CLEAR_SUBSTR = "cwf_stf_gid_clear"
    _PLACEHOLDER_IO   = "<gid_clear_pattern_IO>"
    _PLACEHOLDER_IE   = "<gid_clear_pattern_IE>"

    def _make(name: str) -> PlistEntry:
        return PlistEntry(kind="Pat", name=name, raw=f"   Pat {name};\n")

    io_name: str | None = None
    ie_name: str | None = None

    # 1. User-supplied FILE
    if getattr(args, "gid_clear", None):
        path = Path(args.gid_clear)
        if not path.is_file():
            print(f"  ERROR: --gid-clear file not found: {args.gid_clear}", file=sys.stderr)
        else:
            names = [
                ln.strip() for ln in path.read_text(encoding="utf-8-sig").splitlines()
                if ln.strip() and not ln.strip().startswith("#")
            ]
            for name in names:
                if "5o2" in name and io_name is None:
                    io_name = name
                elif "5o1" in name and ie_name is None:
                    ie_name = name
                else:
                    # No type marker — use as fallback for whichever is still unset
                    if io_name is None:
                        io_name = name
                    if ie_name is None:
                        ie_name = name

    # 2. Search the source plist (only for types still unresolved)
    if io_name is None or ie_name is None:
        for block in plist_file.blocks:
            for e in block.entries:
                if e.kind == "Pat" and _GID_CLEAR_SUBSTR in e.name:
                    if "5o2" in e.name and io_name is None:
                        io_name = e.name
                    elif "5o1" in e.name and ie_name is None:
                        ie_name = e.name
            if io_name and ie_name:
                break

    # 3. Report and fall back to placeholders
    io_entry = _make(io_name if io_name else _PLACEHOLDER_IO)
    ie_entry = _make(ie_name if ie_name else _PLACEHOLDER_IE)

    print(f"  gid_clear IO (sSs/5o2): '{io_entry.name}'")
    print(f"  gid_clear IE (sEs/5o1): '{ie_entry.name}'")
    if io_name is None or ie_name is None:
        print(
            "  INFO: One or both gid_clear patterns unresolved — placeholders written.\n"
            "        Supply --gid-clear FILE or edit the output manually."
        )

    return io_entry, ie_entry
