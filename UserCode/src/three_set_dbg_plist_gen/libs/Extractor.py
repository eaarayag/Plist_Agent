"""
Extractor.py — Identifies PLB chains from a parsed plist file.

Public API
----------
    ChainData     : Holds all data for one PLB chain (PLB + content plists + hotresets).
    PlistExtractor: Stateless helper; call class methods directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from libs.Parser import PlistBlock, PlistFile


# ─── Constants ────────────────────────────────────────────────────────────────

_PRECAT_BASE = "scn_preprecat_cdie_grdt_base_sSs_list"
_PRECAT_TOP  = "scn_preprecat_cdie_grdt_top_sSs_list"

_NON_PLB_PREFIXES = (
    "reset_",
    "scn_preprecat_",
    "pre_precat_",
    "end_gracefully_",
    "endgracefully_",
)


# ─── Data model ───────────────────────────────────────────────────────────────

@dataclass
class ChainData:
    """Holds the full PLB chain needed to generate the three-set variants."""
    plb:              PlistBlock
    structure:        str                    # "standard" | "chico"
    content_plists:   list[PlistBlock]       # ordered, deduplicated
    hotreset_plists:  list[PlistBlock]       # ordered, deduplicated; empty for chico
    precat_variant:   str | None             # "base" | "top" | None (unknown)
    precat_location:  str                    # "hotreset" (standard) | "plb" (chico)


# ─── PlistExtractor ───────────────────────────────────────────────────────────

class PlistExtractor:
    """Stateless helper for identifying and extracting PLB chains."""

    # ── Public ────────────────────────────────────────────────────────────────

    @staticmethod
    def identify_plbs(
        plist_file: PlistFile,
        mode: str,
        plb_names: list[str] | None = None,
    ) -> list[PlistBlock]:
        """
        Identify PLB blocks from the parsed plist file.

        Parameters
        ----------
        plist_file:
            The fully parsed plist file.
        mode:
            ``"all"``      - return every sSs PLB found in the file.
            ``"selected"`` - return only the blocks whose names are in *plb_names*.
            ``"exclude"``  - return every sSs PLB found in the file whose name is
                             NOT in *plb_names*.
        plb_names:
            Required when *mode* is ``"selected"`` or ``"exclude"``.

        Returns
        -------
        list[PlistBlock]
            Identified PLB blocks in file order.
        """
        if mode == "selected":
            result: list[PlistBlock] = []
            for name in (plb_names or []):
                block = plist_file.block_map.get(name)
                if block is None:
                    print(f"  [Extractor] WARNING: PLB not found in file: '{name}' - skipping.")
                else:
                    result.append(block)
            return result

        if mode == "exclude":
            exclude_set: set[str] = set(plb_names or [])
            excluded_found: list[str] = []
            result_ex: list[PlistBlock] = []
            for b in plist_file.blocks:
                if not PlistExtractor._is_plb_candidate(b):
                    continue
                if b.name in exclude_set:
                    excluded_found.append(b.name)
                else:
                    result_ex.append(b)
            # Warn about names in the exclusion list that were never seen in the file
            for name in (plb_names or []):
                if name not in {b.name for b in plist_file.blocks}:
                    print(f"  [Extractor] NOTE: Exclusion name not found in file: '{name}'.")
            if excluded_found:
                print(f"  [Extractor] Excluded {len(excluded_found)} PLB(s) as requested.")
            return result_ex

        # mode == "all"
        return [
            b for b in plist_file.blocks
            if PlistExtractor._is_plb_candidate(b)
        ]

    @staticmethod
    def classify_structure(plb_block: PlistBlock) -> str:
        """
        Classify a PLB as ``"chico"`` or ``"standard"``.

        Chico PLBs embed reset/precat infrastructure entries directly in their
        body.  Standard PLBs call only content plists.

        Returns
        -------
        str
            ``"chico"`` or ``"standard"``.
        """
        for entry in plb_block.entries:
            if entry.kind == "PList" and (
                entry.name.startswith("reset_")
                or entry.name.startswith("scn_preprecat_")
                or entry.name.startswith("pre_precat_")
            ):
                return "chico"
        return "standard"

    @staticmethod
    def find_precat(entries: list) -> str | None:
        """
        Scan *entries* for known precat PList calls.

        Returns ``"base"``, ``"top"``, or ``None`` if no known precat is found.
        """
        for entry in entries:
            if entry.kind == "PList":
                if entry.name == _PRECAT_BASE:
                    return "base"
                if entry.name == _PRECAT_TOP:
                    return "top"
        return None

    @classmethod
    def extract_chain(
        cls,
        plb_block: PlistBlock,
        structure: str,
        plist_file: PlistFile,
    ) -> ChainData:
        """
        Extract the full PLB chain: PLB → content plists → hotreset plists.

        For **standard** structure, each content plist references a hotreset via
        ``[PreBurstPList]``; the hotreset contains the precat entry.

        For **chico** structure, the precat entry lives in the PLB body; there
        are no separate hotreset blocks.

        Parameters
        ----------
        plb_block:
            The PLB block to extract the chain from.
        structure:
            ``"standard"`` or ``"chico"`` (from :meth:`classify_structure`).
        plist_file:
            The full parsed plist file used for lookups.

        Returns
        -------
        ChainData
        """
        if structure == "standard":
            return cls._extract_standard(plb_block, plist_file)
        return cls._extract_chico(plb_block, plist_file)

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _is_plb_candidate(block: PlistBlock) -> bool:
        """
        Return True if *block* looks like a top-level debug PLB.

        Criteria:
          - Block name contains ``"sSs"`` (debug / IO / 5o2 indicator).
          - Block name does NOT match hotreset / reset / precat patterns.
          - All entries are PList kind (no Pat entries).
          - At least one entry name contains ``"_edt_"`` (content-plist marker).
        """
        name = block.name

        if "sSs" not in name:
            return False
        if "_hotreset_" in name:
            return False
        if any(name.startswith(p) for p in _NON_PLB_PREFIXES):
            return False
        if not block.entries:
            return False
        if not all(e.kind == "PList" for e in block.entries):
            return False
        # Must have at least one content plist reference
        if not any("_edt_" in e.name for e in block.entries if e.kind == "PList"):
            return False
        return True

    @staticmethod
    def _extract_standard(plb_block: PlistBlock, plist_file: PlistFile) -> ChainData:
        content_plists:  list[PlistBlock] = []
        hotreset_plists: list[PlistBlock] = []
        seen_content:    set[str]         = set()
        seen_hotreset:   set[str]         = set()

        for entry in plb_block.entries:
            if entry.kind != "PList":
                continue

            cb = plist_file.block_map.get(entry.name)
            if cb is None:
                print(f"  [Extractor] WARNING: Content plist not found: '{entry.name}' - skipping.")
                continue

            if cb.name not in seen_content:
                seen_content.add(cb.name)
                content_plists.append(cb)

                if cb.preburst:
                    if cb.preburst not in seen_hotreset:
                        hr = plist_file.block_map.get(cb.preburst)
                        if hr is None:
                            print(
                                f"  [Extractor] WARNING: Hotreset block not found: "
                                f"'{cb.preburst}' — skipping."
                            )
                        else:
                            seen_hotreset.add(cb.preburst)
                            hotreset_plists.append(hr)
                else:
                    print(
                        f"  [Extractor] WARNING: Content plist '{cb.name}' has no "
                        "PreBurstPList — included with no hotreset reference."
                    )

        # Find precat in the first available hotreset
        precat_variant: str | None = None
        for hr in hotreset_plists:
            precat_variant = PlistExtractor.find_precat(hr.entries)
            if precat_variant:
                break

        return ChainData(
            plb             = plb_block,
            structure       = "standard",
            content_plists  = content_plists,
            hotreset_plists = hotreset_plists,
            precat_variant  = precat_variant,
            precat_location = "hotreset",
        )

    @staticmethod
    def _extract_chico(plb_block: PlistBlock, plist_file: PlistFile) -> ChainData:
        content_plists: list[PlistBlock] = []
        seen_content:   set[str]         = set()

        for entry in plb_block.entries:
            if entry.kind != "PList":
                continue
            # Skip infrastructure entries — they stay in the PLB body
            if any(entry.name.startswith(p) for p in _NON_PLB_PREFIXES):
                continue

            cb = plist_file.block_map.get(entry.name)
            if cb is None:
                print(f"  [Extractor] WARNING: Content plist not found: '{entry.name}' - skipping.")
                continue

            if cb.name not in seen_content:
                seen_content.add(cb.name)
                content_plists.append(cb)

        precat_variant = PlistExtractor.find_precat(plb_block.entries)

        return ChainData(
            plb             = plb_block,
            structure       = "chico",
            content_plists  = content_plists,
            hotreset_plists = [],
            precat_variant  = precat_variant,
            precat_location = "plb",
        )
