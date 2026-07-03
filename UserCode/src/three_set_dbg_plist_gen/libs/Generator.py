"""
Generator.py — Writes the three-set generation result to output files.

Two output files are produced:
    <prefix>.plist             — The generated U3/U4/U5 plist blocks.
    <prefix>_used_plists.list  — Report listing the original PLBs, content plists,
                                 and hotreset plists that were used as sources.

Blocks in the .plist output are section-separated and ordered:
    1. Hotreset blocks  (standard structure only)
    2. Content blocks
    3. PLB blocks

Public API
----------
    ThreeSetGenerator : instantiate once, then call .write_plist() and .write_report().
"""

from __future__ import annotations

import sys
from pathlib import Path

from libs.Parser import PlistBlock


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

_INDENT = "   "


# ─── ThreeSetGenerator ────────────────────────────────────────────────────────

class ThreeSetGenerator:
    """Writes generated plist blocks and usage report to disk."""

    def write_plist(
        self,
        blocks: list[PlistBlock],
        output_path: str | Path,
    ) -> None:
        """
        Write *blocks* to *output_path* as a .plist file.

        The file starts with ``Version 5.0;`` and blocks are separated by
        section-separator comment banners (hotreset / content / PLB).
        Parent directories are created automatically.

        Parameters
        ----------
        blocks:
            All generated U3/U4/U5 plist blocks accumulated across all PLB chains.
        output_path:
            Destination .plist file path.
        """
        if not blocks:
            print("[Generator] No blocks to write - .plist output will not be created.")
            return

        lines: list[str] = ["Version 5.0;\n", "\n"]

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

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text("".join(lines), encoding="utf-8")
        except OSError as exc:
            print(f"[Generator] Could not write .plist file: {exc}", file=sys.stderr)
            raise

        print(f"[Generator] Written {len(blocks)} block(s) -> {path}")

    def write_report(
        self,
        used_plbs:      list[str],
        used_content:   list[str],
        used_hotreset:  list[str],
        report_path:    str | Path,
    ) -> None:
        """
        Write the used-plists report to *report_path*.

        The file contains three labelled sections listing the ORIGINAL (source)
        plist names that fed into the generation — not the generated U3/U4/U5 names.

        Parameters
        ----------
        used_plbs:
            Original PLB names processed.
        used_content:
            Original content plist names used as sources.
        used_hotreset:
            Original hotreset plist names used as sources.
        report_path:
            Destination .list file path.
        """
        lines: list[str] = []

        lines.append("# PLBs used in generation\n")
        for name in used_plbs:
            lines.append(f"{name}\n")
        lines.append("\n")

        lines.append("# Content Plists used in generation\n")
        for name in used_content:
            lines.append(f"{name}\n")
        lines.append("\n")

        lines.append("# Hotreset Plists used in generation\n")
        for name in used_hotreset:
            lines.append(f"{name}\n")

        path = Path(report_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text("".join(lines), encoding="utf-8")
        except OSError as exc:
            print(f"[Generator] Could not write report file: {exc}", file=sys.stderr)
            raise

        print(f"[Generator] Report written -> {path}")

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _classify(
        blocks: list[PlistBlock],
    ) -> tuple[list[PlistBlock], list[PlistBlock], list[PlistBlock]]:
        """Split *blocks* into (hotreset, content, plb) buckets for sectioning."""
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

        The header is taken from ``block.raw_header`` (built by the Transformer).
        Entries are re-rendered with a consistent three-space indent.
        Comment entries (``#Pat``) are rendered as ``#Pat <name>;``.
        """
        lines: list[str] = []

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


# ─── Block classification helpers ─────────────────────────────────────────────

def _is_hotreset(block: PlistBlock) -> bool:
    name = block.name
    return (
        "_hotreset_" in name
        or name.startswith("reset_")
        or name.startswith("pre_precat_")
        or name.startswith("scn_preprecat_")
        or name.startswith("end_gracefully_")
        or name.startswith("endgracefully_")
    )


def _is_plb(block: PlistBlock) -> bool:
    """A PLB has no Pat entries and is not a hotreset block."""
    if _is_hotreset(block):
        return False
    return all(e.kind == "PList" for e in block.entries)
