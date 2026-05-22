"""
Parser.py — Tokenizes a .plist file into structured Python objects.

Public API
----------
    PlistEntry  : A single line inside a GlobalPList block (Pat or PList call).
    PlistBlock  : One complete GlobalPList block.
    PlistFile   : The entire parsed file (version + all blocks).
    PlistParser : Stateless parser; call PlistParser.parse(path) -> PlistFile.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


# ─── Data model ───────────────────────────────────────────────────────────────

@dataclass
class PlistEntry:
    """A single executable line inside a GlobalPList block."""
    kind: str        # "PList" or "Pat"
    name: str        # bare name (no keyword, no semicolon)
    raw:  str        # original line as it appeared in the file (with newline)


@dataclass
class PlistBlock:
    """One complete GlobalPList ... { ... } block."""
    name:        str                       # bare block name
    options_raw: str                       # everything between name and "{"  (e.g. "[Flatten]")
    preburst:    str | None                # name from [PreBurstPList <name>] or None
    postburst:   str | None                # name from [PostBurstPList <name>] or None
    entries:     list[PlistEntry]          # ordered body entries
    raw_header:  str                       # original "GlobalPList ..." header line (with newline)

    # ── Convenience helpers ──────────────────────────────────────────────────

    def plist_calls(self) -> list[str]:
        """Return the names of all PList entries in this block."""
        return [e.name for e in self.entries if e.kind == "PList"]

    def pat_calls(self) -> list[str]:
        """Return the names of all Pat entries in this block."""
        return [e.name for e in self.entries if e.kind == "Pat"]


@dataclass
class PlistFile:
    """The entire parsed .plist file."""
    version:   str | None              # e.g. "5.0", or None if not present
    blocks:    list[PlistBlock]        # ordered list of all blocks
    block_map: dict[str, PlistBlock]   # name -> block (for O(1) lookup)


# ─── Regex patterns ───────────────────────────────────────────────────────────

_RE_VERSION    = re.compile(r"^\s*Version\s+([\d.]+)\s*;")
_RE_BLOCK_OPEN = re.compile(r"^\s*GlobalPList\s+(\S+)(.*?)\{")
_RE_PLIST_CALL = re.compile(r"^\s*PList\s+(\S+)\s*;")
_RE_PAT_CALL   = re.compile(r"^\s*Pat\s+(\S+)\s*;")
_RE_PREBURST   = re.compile(r"\[\s*PreBurstPList\s+(\S+)\s*\]")
_RE_POSTBURST  = re.compile(r"\[\s*PostBurstPList\s+(\S+)\s*\]")


# ─── Parser ───────────────────────────────────────────────────────────────────

class PlistParser:
    """Stateless .plist file parser.  All logic is in the class method ``parse``."""

    @classmethod
    def parse(cls, file_path: str | Path) -> PlistFile:
        """
        Read *file_path* and return a :class:`PlistFile`.

        The parser is line-by-line and tolerant of non-standard spacing.
        It does NOT validate plist semantics — unknown lines are silently skipped.

        Parameters
        ----------
        file_path:
            Path to the ``.plist`` file to read.

        Returns
        -------
        PlistFile
            Parsed representation of the file.

        Raises
        ------
        FileNotFoundError
            If *file_path* does not exist.
        """
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")

        version: str | None = None
        blocks:  list[PlistBlock] = []

        # State for the current open block
        current_name:    str | None = None
        current_options: str        = ""
        current_header:  str        = ""
        current_entries: list[PlistEntry] = []
        inside_block = False

        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for raw_line in fh:
                line = raw_line  # keep original for storage

                # ── Version declaration ───────────────────────────────────────
                if not inside_block:
                    m = _RE_VERSION.match(line)
                    if m:
                        version = m.group(1)
                        continue

                # ── Block open ────────────────────────────────────────────────
                if not inside_block:
                    m = _RE_BLOCK_OPEN.match(line)
                    if m:
                        current_name    = m.group(1).strip()
                        current_options = m.group(2).strip()
                        current_header  = raw_line
                        current_entries = []
                        inside_block    = True
                    continue

                # ── Inside a block ────────────────────────────────────────────
                stripped = line.strip()

                if stripped == "}":
                    # Close the current block
                    preburst  = cls._extract_option(_RE_PREBURST,  current_options)
                    postburst = cls._extract_option(_RE_POSTBURST, current_options)

                    block = PlistBlock(
                        name        = current_name,
                        options_raw = current_options,
                        preburst    = preburst,
                        postburst   = postburst,
                        entries     = current_entries,
                        raw_header  = current_header,
                    )
                    blocks.append(block)
                    inside_block    = False
                    current_name    = None
                    current_options = ""
                    current_header  = ""
                    current_entries = []
                    continue

                # PList call
                m = _RE_PLIST_CALL.match(line)
                if m:
                    current_entries.append(
                        PlistEntry(kind="PList", name=m.group(1), raw=raw_line)
                    )
                    continue

                # Pat call
                m = _RE_PAT_CALL.match(line)
                if m:
                    current_entries.append(
                        PlistEntry(kind="Pat", name=m.group(1), raw=raw_line)
                    )
                    continue

                # Any other line inside a block is silently skipped

        block_map = {b.name: b for b in blocks}
        return PlistFile(version=version, blocks=blocks, block_map=block_map)

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _extract_option(pattern: re.Pattern, options_str: str) -> str | None:
        """Return the first capture group of *pattern* applied to *options_str*, or None."""
        m = pattern.search(options_str)
        return m.group(1) if m else None
