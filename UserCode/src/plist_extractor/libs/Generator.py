"""
Generator.py — Writes the extraction result to a .plist output file.

The output file always starts with:
    Version 5.0;

Blocks are written in the order they were provided (hotreset → content → PLB).
Optional section-separator comments are inserted between groups so the file is
easy to read and diff.

Public API
----------
    PlistGenerator : instantiate once, then call .write(blocks, output_path).
"""

from __future__ import annotations

import sys
from pathlib import Path

from libs.Parser import PlistBlock, PlistEntry


# ─── Section-separator templates ─────────────────────────────────────────────

_SEP_HOTRESET = [
    "#--------------------#\n",
    "#    HOTRESET        #\n",
    "#--------------------#\n",
]

_SEP_CONTENT = [
    "#--------------------#\n",
    "# PARTITIONS CONTENT #\n",
    "#--------------------#\n",
]

_SEP_PLB = [
    "#--------------------#\n",
    "# PLB CALLS GROUPING #\n",
    "#--------------------#\n",
]

_INDENT = "   "  # three-space indent, consistent with standard .plist formatting


# ─── PlistGenerator ───────────────────────────────────────────────────────────

class PlistGenerator:
    """
    Writes a list of :class:`~libs.Parser.PlistBlock` objects to a ``.plist`` file.

    The generator reconstructs each block from its stored data so that the
    output is consistently formatted even if the original file had irregular
    spacing.
    """

    def write(self, blocks: list[PlistBlock], output_path: str | Path) -> None:
        """
        Write *blocks* to *output_path*.

        Parameters
        ----------
        blocks:
            Ordered list of blocks as returned by
            :meth:`~libs.Extractor.PlistExtractor.extract`.
        output_path:
            Destination file path.  Parent directories must exist.

        Raises
        ------
        OSError
            If the file cannot be written.
        """
        if not blocks:
            print("[Generator] No blocks to write — output file will not be created.")
            return

        lines: list[str] = []
        lines.append("Version 5.0;\n")
        lines.append("\n")

        # Classify blocks into hotreset / content / plb buckets for separators
        hotresets, content, plbs = self._classify(blocks)

        if hotresets:
            lines.extend(_SEP_HOTRESET)
            lines.append("\n")
            for b in hotresets:
                lines.extend(self._render_block(b))
                lines.append("\n")

        if content:
            lines.extend(_SEP_CONTENT)
            lines.append("\n")
            for b in content:
                lines.extend(self._render_block(b))
                lines.append("\n")

        if plbs:
            lines.extend(_SEP_PLB)
            lines.append("\n")
            for b in plbs:
                lines.extend(self._render_block(b))
                lines.append("\n")

        try:
            Path(output_path).write_text("".join(lines), encoding="utf-8")
        except OSError as exc:
            print(f"[Generator] Could not write output file: {exc}", file=sys.stderr)
            raise

        print(f"[Generator] Written {len(blocks)} block(s) → {output_path}")

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _classify(
        blocks: list[PlistBlock],
    ) -> tuple[list[PlistBlock], list[PlistBlock], list[PlistBlock]]:
        """
        Split *blocks* into (hotreset, content, plb) buckets.

        Classification rules:
          - Block name contains ``"_hotreset_"`` or starts with ``"reset_"``
            or starts with ``"pre_precat_"`` / ``"scn_preprecat_"``
            → hotreset bucket
          - Block is a PLB when it was trimmed (i.e. all PList entries are
            content plists — heuristic: PLB has no Pat entries and is not a
            hotreset block).  In practice, any block with only PList entries
            that does NOT contain ``"_hotreset_"`` and is not a reset/precat
            block AND whose entries include content-plist names is a PLB.
          - Everything else → content bucket.

        The simplest robust rule: let the *caller* (Extractor) guarantee
        the order hotreset → content → PLB.  We only need to detect the
        hotreset blocks so we can insert the right separator.
        """
        hotresets: list[PlistBlock] = []
        content:   list[PlistBlock] = []
        plbs:      list[PlistBlock] = []

        for b in blocks:
            if _is_hotreset(b):
                hotresets.append(b)
            elif _is_plb(b):
                plbs.append(b)
            else:
                content.append(b)

        return hotresets, content, plbs

    @staticmethod
    def _render_block(block: PlistBlock) -> list[str]:
        """
        Reconstruct the text lines for *block*.

        The header is taken verbatim from ``block.raw_header`` to preserve the
        original bracket options ([PreBurstPList ...], [PostBurstPList ...],
        [Flatten], etc.).  Entries are re-rendered with a consistent three-space
        indent.
        """
        lines: list[str] = []

        # Header — strip trailing whitespace/newline then re-add newline + space + {
        header = block.raw_header.rstrip()
        # Ensure the header ends with " {" (it should already, but be safe)
        if not header.endswith("{"):
            header = header + " {"
        lines.append(header + "\n")

        for entry in block.entries:
            lines.append(f"{_INDENT}{entry.kind} {entry.name};\n")

        lines.append("}\n")
        return lines


# ─── Block classification helpers ─────────────────────────────────────────────

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
    """
    Return True if *block* looks like a PLB (main plist).

    A PLB:
      - Has no Pat entries, and
      - Is not classified as a hotreset block.
    """
    if _is_hotreset(block):
        return False
    return all(e.kind == "PList" for e in block.entries)
