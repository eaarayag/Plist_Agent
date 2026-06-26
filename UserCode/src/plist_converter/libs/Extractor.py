"""
Extractor.py — Locates and collects the plist blocks needed for conversion.

Given a parsed PlistFile, a list of PLB names, and a conversion mode, the
extractor walks the call tree and returns the complete set of blocks required
to write the output file.  No structural transformation is performed here —
blocks are returned in their original form.

Modes
-----
default-to-chico
    For each PLB:
      1. Collect content plists (PList entries that are NOT reset/precat/end_gracefully).
      2. For each content plist, look up its hotreset block via [PreBurstPList].
    Return order: hotreset blocks → content blocks → PLB blocks.

chico-to-default
    For each PLB:
      1. Collect content plists (PList entries, skipping reset/precat/end_gracefully).
    Return order: content blocks → PLB blocks.

Public API
----------
    PlistConverterExtractor : instantiate with (plist_file, plb_names, mode),
                              then call .extract() → list[PlistBlock].
"""

from __future__ import annotations

from src.plist_extractor.libs.Parser import PlistBlock, PlistFile

# Conversion mode constants
MODE_DEFAULT_TO_CHICO = "default-to-chico"
MODE_CHICO_TO_DEFAULT = "chico-to-default"


# ─── Name classification helpers ─────────────────────────────────────────────

def _is_reset_or_precat(name: str) -> bool:
    return (
        name.startswith("reset_")
        or name.startswith("pre_precat_")
        or name.startswith("scn_preprecat_")
    )


def _is_end_gracefully(name: str) -> bool:
    return name.startswith("end_gracefully_") or name.startswith("endgracefully_")


def _is_non_content(name: str) -> bool:
    """Return True for entries that are structural glue, not real content plists."""
    return _is_reset_or_precat(name) or _is_end_gracefully(name)


# ─── PlistConverterExtractor ─────────────────────────────────────────────────

class PlistConverterExtractor:
    """
    Extracts plist blocks needed for a structure conversion.

    Parameters
    ----------
    plist_file:
        A :class:`~libs.Parser.PlistFile` produced by PlistParser.
    plb_names:
        List of PLB / main-plist names to process.
    mode:
        One of ``"default-to-chico"`` or ``"chico-to-default"``.
    """

    def __init__(
        self,
        plist_file: PlistFile,
        plb_names:  list[str],
        mode:       str,
    ) -> None:
        self._file      = plist_file
        self._plb_names = plb_names
        self._mode      = mode

    # ── Public ────────────────────────────────────────────────────────────────

    def extract(self) -> list[PlistBlock]:
        """
        Run extraction and return ordered blocks ready for the Generator.

        default-to-chico : hotreset → content → PLB
        chico-to-default : content → PLB
        """
        if self._mode == MODE_DEFAULT_TO_CHICO:
            return self._extract_default_to_chico()
        else:
            return self._extract_chico_to_default()

    # ── default-to-chico ──────────────────────────────────────────────────────

    def _extract_default_to_chico(self) -> list[PlistBlock]:
        hotreset_blocks: list[PlistBlock] = []
        content_blocks:  list[PlistBlock] = []
        plb_blocks:      list[PlistBlock] = []

        seen_hotreset: set[str] = set()
        seen_content:  set[str] = set()

        for plb_name in self._plb_names:
            plb = self._lookup(plb_name)
            if plb is None:
                continue

            plb_blocks.append(plb)

            # Collect content plists: PList entries that are not structural glue
            for entry in plb.entries:
                if entry.kind != "PList":
                    continue
                if _is_non_content(entry.name):
                    continue

                content_block = self._lookup(entry.name)
                if content_block is None:
                    continue

                if content_block.name not in seen_content:
                    content_blocks.append(content_block)
                    seen_content.add(content_block.name)

                # Collect hotreset via [PreBurstPList]
                if content_block.preburst:
                    hr = self._lookup(content_block.preburst)
                    if hr is not None and hr.name not in seen_hotreset:
                        hotreset_blocks.append(hr)
                        seen_hotreset.add(hr.name)

        return hotreset_blocks + content_blocks + plb_blocks

    # ── chico-to-default ──────────────────────────────────────────────────────

    def _extract_chico_to_default(self) -> list[PlistBlock]:
        content_blocks: list[PlistBlock] = []
        plb_blocks:     list[PlistBlock] = []

        seen_content: set[str] = set()

        for plb_name in self._plb_names:
            plb = self._lookup(plb_name)
            if plb is None:
                continue

            plb_blocks.append(plb)

            # Collect content plists: PList entries that are not structural glue
            for entry in plb.entries:
                if entry.kind != "PList":
                    continue
                if _is_non_content(entry.name):
                    continue

                content_block = self._lookup(entry.name)
                if content_block is None:
                    continue

                if content_block.name not in seen_content:
                    content_blocks.append(content_block)
                    seen_content.add(content_block.name)

        return content_blocks + plb_blocks

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _lookup(self, name: str) -> PlistBlock | None:
        """Return the block for *name* or None, printing a warning if missing."""
        block = self._file.block_map.get(name)
        if block is None:
            print(f"  WARNING: Block not found in source file: '{name}' — skipping.")
        return block
