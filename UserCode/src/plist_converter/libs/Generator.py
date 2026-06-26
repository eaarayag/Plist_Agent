"""
Generator.py — Writes extracted plist blocks to an output .plist file.

The output file always starts with:
    Version 5.0;

Blocks are written in the order provided.  Each block header is taken verbatim
from the parsed raw_header to preserve all bracket options ([PreBurstPList ...],
[PostBurstPList ...], [Flatten], etc.).  Entries are re-rendered with a
consistent three-space indent.  Commented Pat entries (#Pat) are preserved.

Public API
----------
    PlistConverterGenerator : instantiate once, then call .write(blocks, output_path).
"""

from __future__ import annotations

import sys
from pathlib import Path

from src.plist_extractor.libs.Parser import PlistBlock

_INDENT = "   "  # three-space indent, consistent with standard .plist formatting


# ─── PlistConverterGenerator ─────────────────────────────────────────────────

class PlistConverterGenerator:
    """Writes a list of PlistBlock objects to a .plist file."""

    def write(self, blocks: list[PlistBlock], output_path: str | Path) -> None:
        """
        Write *blocks* to *output_path*.

        Parameters
        ----------
        blocks:
            Ordered list of blocks as returned by PlistConverterExtractor.extract().
        output_path:
            Destination file path.  Parent directory must exist.

        Raises
        ------
        OSError
            If the file cannot be written.
        """
        if not blocks:
            print("[Generator] No blocks to write — output file will not be created.")
            return

        output_path = Path(output_path)
        lines: list[str] = []
        lines.append("Version 5.0;\n")
        lines.append("\n")

        for block in blocks:
            lines.extend(self._render_block(block))
            lines.append("\n")

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("".join(lines), encoding="utf-8")
        except OSError as exc:
            print(f"[Generator] ERROR writing output: {exc}", file=sys.stderr)
            raise

        print(f"[Generator] Written {len(blocks)} block(s) → {output_path}")

    @staticmethod
    def _render_block(block: PlistBlock) -> list[str]:
        """Reconstruct the text lines for *block* from its parsed data."""
        lines: list[str] = []

        # Header verbatim (stripped + re-terminated with newline)
        header = block.raw_header.rstrip()
        if not header.endswith("{"):
            header = header + " {"
        lines.append(header + "\n")

        for entry in block.entries:
            if entry.kind == "comment":
                lines.append(f"{_INDENT}#Pat {entry.name};\n")
            else:
                lines.append(f"{_INDENT}{entry.kind} {entry.name};\n")

        lines.append("}\n")
        return lines


# ─── Block classification helpers (used by app_runner for progress reporting) ─

def _is_hotreset(block: PlistBlock) -> bool:
    """Return True if *block* is a hotreset, reset, or precat block."""
    name = block.name
    return (
        "_hotreset_" in name
        or name.startswith("reset_")
        or name.startswith("pre_precat_")
        or name.startswith("scn_preprecat_")
        or name.startswith("endgracefully_")
        or name.startswith("end_gracefully_")
    )


def _is_plb(block: PlistBlock) -> bool:
    """Return True if *block* is a PLB (all entries are PList/comment, not a hotreset)."""
    if _is_hotreset(block):
        return False
    return all(e.kind in ("PList", "comment") for e in block.entries)
