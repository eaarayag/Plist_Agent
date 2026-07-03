"""
app_runner.py — Orchestrates the three-set debug plist generation pipeline.

Lifecycle:
    setup()    — Validate inputs, resolve output path, start console logging.
    start()    — Parse plist, identify PLBs, extract chains, generate variants.
    shutdown() — Write output .plist, report .list, and .log files; print summary.
    run()      — Calls setup() → start() → shutdown().

Output deduplication
--------------------
A content plist or hotreset plist may be referenced by more than one PLB.
Generated blocks are de-duplicated by name so each GlobalPList declaration
appears exactly once in the output file.

Log file
--------
All console output is captured to <output_prefix>.log.
The log includes a final summary section with skipped PLBs and their reasons.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from libs.Parser import PlistParser
from libs.Extractor import PlistExtractor
from libs.Transformer import PlistSplitter
from libs.Generator import ThreeSetGenerator


# ─── Stdout tee ───────────────────────────────────────────────────────────────

class _TeeWriter:
    """Write to both the original stdout and an in-memory buffer simultaneously."""

    def __init__(self, original) -> None:
        self._original = original
        self._buffer   = io.StringIO()

    def write(self, text: str) -> int:
        try:
            self._original.write(text)
        except (UnicodeEncodeError, UnicodeDecodeError):
            # Terminal codec is narrower than UTF-8; fall back to replacement chars
            enc = getattr(self._original, "encoding", "utf-8") or "utf-8"
            self._original.write(text.encode(enc, errors="replace").decode(enc))
        self._buffer.write(text)
        return len(text)

    def flush(self) -> None:
        self._original.flush()

    def getvalue(self) -> str:
        return self._buffer.getvalue()


# ─── AppRunner ────────────────────────────────────────────────────────────────

class AppRunner:
    def __init__(self, args) -> None:
        self.args = args

        # Resolved at setup()
        self._input_path:    Path | None = None
        self._output_prefix: Path | None = None
        self._plb_names:     list[str]   = []

        # Accumulated during start()
        self._all_blocks:       list                 = []
        self._seen_block_names: set[str]             = set()
        self._used_plbs:        list[str]            = []
        self._used_content:     list[str]            = []
        self._used_hotreset:    list[str]            = []
        self._processed:        int                  = 0
        self._skipped:          int                  = 0
        self._dup_count:        int                  = 0
        self._skipped_items:    list[tuple[str,str]] = []

        # Logging
        self._tee: _TeeWriter | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def setup(self) -> None:
        """Validate inputs, resolve output path, and start capturing console output."""
        # Start teeing stdout so all output is captured for the log file.
        self._tee = _TeeWriter(sys.stdout)
        sys.stdout = self._tee

        self._input_path = Path(self.args.input)
        if not self._input_path.is_file():
            print(f"[Error] Input file not found: {self._input_path}", file=sys.stderr)
            sys.exit(1)

        if self.args.mode in ("selected", "exclude"):
            list_path = Path(self.args.list)
            if not list_path.is_file():
                print(f"[Error] PLB list file not found: {list_path}", file=sys.stderr)
                sys.exit(1)
            raw_lines = list_path.read_text(encoding="utf-8-sig").splitlines()
            self._plb_names = [
                ln.strip() for ln in raw_lines
                if ln.strip() and not ln.strip().startswith("#")
            ]
            if not self._plb_names:
                print(f"[Error] PLB list file contains no entries: {list_path}", file=sys.stderr)
                sys.exit(1)

        # Resolve output prefix
        if self.args.output:
            candidate = Path(self.args.output)
            # Treat as directory if it ends with a separator or already is a directory
            if str(self.args.output).endswith(("/", "\\")) or candidate.is_dir():
                self._output_prefix = candidate / (self._input_path.stem + "_three_set")
            else:
                self._output_prefix = candidate
        else:
            self._output_prefix = (
                self._input_path.parent / (self._input_path.stem + "_three_set")
            )

        print(f"[Setup] Input:  {self._input_path}")
        print(f"[Setup] Mode:   {self.args.mode}")
        if self.args.mode == "selected":
            print(f"[Setup] Include: {len(self._plb_names)} name(s) from list file")
        elif self.args.mode == "exclude":
            print(f"[Setup] Exclude: {len(self._plb_names)} name(s) from list file")
        print(f"[Setup] Output: {self._output_prefix}.plist")
        print(f"[Setup] Log:    {self._output_prefix}.log")

    def start(self) -> None:
        """Parse the plist file and generate all three-set variant blocks."""
        print(f"\n[Start] Parsing {self._input_path.name} ...")
        plist_file = PlistParser.parse(self._input_path)
        print(f"[Start] Found {len(plist_file.blocks)} total block(s) in file.")

        extractor = PlistExtractor()
        plbs = extractor.identify_plbs(
            plist_file,
            mode      = self.args.mode,
            plb_names = self._plb_names if self.args.mode in ("selected", "exclude") else None,
        )
        print(f"[Start] Identified {len(plbs)} PLB(s) to process.\n")

        splitter = PlistSplitter()

        for plb in plbs:
            print(f"  PLB: {plb.name}")

            structure = extractor.classify_structure(plb)
            print(f"    Structure:   {structure}")

            chain = extractor.extract_chain(plb, structure, plist_file)

            if not chain.content_plists:
                reason = "no content plists found in chain"
                print(f"    WARNING: {reason} - skipping.")
                self._skipped += 1
                self._skipped_items.append((plb.name, reason))
                continue

            if chain.precat_variant is None:
                reason = "no known precat (scn_preprecat_cdie_grdt_base/top_sSs_list) found"
                print(f"    WARNING: {reason} - skipping.")
                self._skipped += 1
                self._skipped_items.append((plb.name, reason))
                continue

            print(f"    Precat:      {chain.precat_variant} ({chain.precat_location})")
            print(
                f"    Content:     {len(chain.content_plists)} plist(s), "
                f"Hotreset: {len(chain.hotreset_plists)} plist(s)"
            )

            variant_sets = splitter.generate_variants(chain)
            added = 0
            deduped = 0
            for variant_blocks in variant_sets:
                for block in variant_blocks:
                    if block.name not in self._seen_block_names:
                        self._seen_block_names.add(block.name)
                        self._all_blocks.append(block)
                        added += 1
                    else:
                        deduped += 1
            if deduped:
                print(f"    Deduplicated: {deduped} block(s) already defined by a previous PLB.")
            self._dup_count += deduped

            # Track original (source) names for the report
            self._used_plbs.append(plb.name)
            for cb in chain.content_plists:
                if cb.name not in self._used_content:
                    self._used_content.append(cb.name)
            for hr in chain.hotreset_plists:
                if hr.name not in self._used_hotreset:
                    self._used_hotreset.append(hr.name)

            self._processed += 1

        print(
            f"\n[Start] Done - {self._processed} PLB(s) processed, "
            f"{self._skipped} skipped."
        )

    def shutdown(self) -> None:
        """Write the output .plist, report .list, and log files; print final summary."""
        if not self._all_blocks:
            print("\n[Shutdown] No blocks were generated - nothing to write.")
            self._write_log()
            return

        generator = ThreeSetGenerator()

        plist_out  = Path(str(self._output_prefix) + ".plist")
        report_out = Path(str(self._output_prefix) + "_used_plists.list")

        print()
        generator.write_plist(self._all_blocks, plist_out)
        generator.write_report(
            used_plbs     = self._used_plbs,
            used_content  = self._used_content,
            used_hotreset = self._used_hotreset,
            report_path   = report_out,
        )

        # ── Final summary ─────────────────────────────────────────────────────
        print()
        print("[Summary] " + "-" * 52)
        print(f"  PLBs processed  : {self._processed}")
        print(f"  PLBs skipped    : {self._skipped}")
        print(f"  Blocks written  : {len(self._all_blocks)}")
        if self._dup_count:
            print(
                f"  Deduplicated    : {self._dup_count} block(s) suppressed "
                "(already defined by a previous PLB)"
            )

        if self._skipped_items:
            print()
            print("  Skipped PLBs:")
            for name, reason in self._skipped_items:
                print(f"    • {name}")
                print(f"      Reason : {reason}")

        print()
        print(f"  Output .plist   : {plist_out}")
        print(f"  Report .list    : {report_out}")

        self._write_log()

    def run(self) -> None:
        """Execute the full application lifecycle: setup → start → shutdown."""
        try:
            self.setup()
            self.start()
            self.shutdown()
        except SystemExit:
            # Ensure log is flushed even on early exit (e.g. invalid arguments)
            self._write_log()
            raise

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _write_log(self) -> None:
        """
        Restore real stdout and write all captured console output to a .log file.

        Safe to call multiple times — subsequent calls are no-ops.
        """
        if self._tee is None:
            return

        log_content = self._tee.getvalue()
        log_path    = (
            Path(str(self._output_prefix) + ".log")
            if self._output_prefix is not None
            else None
        )

        # Append the "log written" line to the captured content before saving
        if log_path is not None:
            log_content += f"\n[Log]    Written -> {log_path}\n"

        # Restore real stdout before writing so any subsequent prints go to terminal
        sys.stdout   = self._tee._original
        self._tee    = None  # Prevent double-write

        if log_path is None:
            return

        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(log_content, encoding="utf-8")
            print(f"[Log]    Written -> {log_path}")
        except Exception as exc:
            print(f"[Log]    Could not write log file: {exc}", file=sys.stderr)
