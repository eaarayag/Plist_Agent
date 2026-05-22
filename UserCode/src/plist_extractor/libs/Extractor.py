"""
Extractor.py — Orchestrates the full extraction of a plist call tree.

Given a parsed PlistFile and a configured PlistMatcher the extractor:

  1. Finds all content plists whose name satisfies the matcher.
  2. Finds every PLB (main plist) that calls at least one of those content plists.
  3. Detects the plist design type for each PLB:
       - "chico"   : PLB body contains reset_* / pre_precat_* PList calls directly.
       - "default" : PLB body contains only content-plist PList calls.
  4. Trims each PLB so it contains only the reset groups and content-plist calls
     that belong to the requested partition set.
  5. For "default" design: collects hotreset plists referenced via
     [PreBurstPList <name>] on the content plists.
  6. Returns an ordered list of blocks ready for the Generator:
       hotreset blocks → content plist blocks → trimmed PLB blocks

Public API
----------
    PlistExtractor : instantiate with (plist_file, matcher), then call .extract().
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from libs.Parser  import PlistBlock, PlistEntry, PlistFile
from libs.Matcher import PlistMatcher


# ─── Reset-group model ────────────────────────────────────────────────────────

@dataclass
class _ResetGroup:
    """One contiguous 'reset → precat → content plists' block inside a chico PLB."""
    reset_entries:   list[PlistEntry] = field(default_factory=list)
    precat_entries:  list[PlistEntry] = field(default_factory=list)
    content_entries: list[PlistEntry] = field(default_factory=list)
    separator:       PlistEntry | None = None   # the end_gracefully_ entry that follows this group


# ─── PlistExtractor ───────────────────────────────────────────────────────────

class PlistExtractor:
    """
    Extracts the full plist call tree for the partitions / criteria described
    by *matcher* from *plist_file*.

    Parameters
    ----------
    plist_file:
        A :class:`~libs.Parser.PlistFile` produced by :class:`~libs.Parser.PlistParser`.
    matcher:
        A configured :class:`~libs.Matcher.PlistMatcher`.
    """

    def __init__(self, plist_file: PlistFile, matcher: PlistMatcher) -> None:
        self._file    = plist_file
        self._matcher = matcher

    # ── Public ────────────────────────────────────────────────────────────────

    def extract(self) -> list[PlistBlock]:
        """
        Run the full extraction pipeline and return an ordered list of
        :class:`~libs.Parser.PlistBlock` objects ready for the Generator.

        Order: hotreset blocks → content plist blocks → PLB blocks.
        """
        content_blocks = self._find_content_plists()
        if not content_blocks:
            return []

        content_names = {b.name for b in content_blocks}

        plb_blocks = self._find_plbs(content_names)

        trimmed_plbs: list[PlistBlock] = []
        hotreset_blocks: list[PlistBlock] = []

        for plb in plb_blocks:
            design = self._detect_design(plb)
            trimmed = self._trim_plb(plb, content_names, design)
            trimmed_plbs.append(trimmed)

            if design == "default":
                hotreset_blocks.extend(self._collect_hotresets(content_blocks))

        # Deduplicate hotreset blocks (preserve order)
        seen_hr: set[str] = set()
        unique_hotreset: list[PlistBlock] = []
        for b in hotreset_blocks:
            if b.name not in seen_hr:
                unique_hotreset.append(b)
                seen_hr.add(b.name)

        return unique_hotreset + content_blocks + trimmed_plbs

    # ── Step 1: find content plists ───────────────────────────────────────────

    def _find_content_plists(self) -> list[PlistBlock]:
        """Return all blocks whose name satisfies the matcher."""
        return [b for b in self._file.blocks if self._matcher.matches(b.name)]

    # ── Step 2: find PLBs ─────────────────────────────────────────────────────

    def _find_plbs(self, content_names: set[str]) -> list[PlistBlock]:
        """
        Return all blocks that call at least one name in *content_names* via a
        ``PList`` entry.  These are the PLB / main-plist blocks.
        """
        result: list[PlistBlock] = []
        for block in self._file.blocks:
            calls = {e.name for e in block.entries if e.kind == "PList"}
            if calls & content_names:
                result.append(block)
        return result

    # ── Step 3: detect design ─────────────────────────────────────────────────

    @staticmethod
    def _detect_design(plb: PlistBlock) -> str:
        """
        Return ``"chico"`` if the PLB body contains ``reset_*`` or ``pre_precat_*``
        / ``scn_preprecat_*`` entries; otherwise return ``"default"``.
        """
        for entry in plb.entries:
            if entry.kind == "PList" and (
                entry.name.startswith("reset_")
                or entry.name.startswith("pre_precat_")
                or entry.name.startswith("scn_preprecat_")
            ):
                return "chico"
        return "default"

    # ── Step 4: trim PLB ──────────────────────────────────────────────────────

    def _trim_plb(
        self,
        plb:           PlistBlock,
        content_names: set[str],
        design:        str,
    ) -> PlistBlock:
        """
        Return a *copy* of *plb* whose entries contain only the parts relevant
        to *content_names*.

        Chico design
        ------------
        The PLB body is split into "reset groups" separated by ``end_gracefully_*``
        entries.  Within each group only entries in *content_names* are kept.
        Groups whose filtered content is empty are dropped entirely.
        ``end_gracefully`` separators are re-inserted only between consecutive
        kept groups.

        Default design
        --------------
        All entries not in *content_names* are removed.
        """
        trimmed = copy.copy(plb)
        trimmed.entries = list(plb.entries)  # shallow copy of list

        if design == "chico":
            trimmed.entries = self._trim_chico(plb.entries, content_names)
        else:
            trimmed.entries = self._trim_default(plb.entries, content_names)

        return trimmed

    # ── Chico trimming ────────────────────────────────────────────────────────

    @staticmethod
    def _trim_chico(
        entries:       list[PlistEntry],
        content_names: set[str],
    ) -> list[PlistEntry]:
        """
        Split PLB entries into reset groups; keep only those groups that contain
        at least one *content_names* call; re-insert separators only between
        consecutive kept groups.
        """
        groups = PlistExtractor._parse_reset_groups(entries)

        # Filter content entries inside each group and drop empty groups
        kept: list[_ResetGroup] = []
        for g in groups:
            filtered = [e for e in g.content_entries if e.name in content_names]
            if filtered:
                g.content_entries = filtered
                kept.append(g)

        if not kept:
            return []

        # Rebuild entry list
        result: list[PlistEntry] = []
        for idx, g in enumerate(kept):
            result.extend(g.reset_entries)
            result.extend(g.precat_entries)
            result.extend(g.content_entries)
            # Add separator only when another group follows
            if idx < len(kept) - 1 and g.separator is not None:
                result.append(g.separator)

        return result

    @staticmethod
    def _parse_reset_groups(entries: list[PlistEntry]) -> list[_ResetGroup]:
        """
        Parse an entry list into :class:`_ResetGroup` objects.

        Rules:
          - A ``reset_*`` entry always starts a new group (even if the current
            group already has reset entries — handles back-to-back resets).
          - ``pre_precat_*`` / ``scn_preprecat_*`` entries belong to the current
            group's precat sequence.
          - ``end_gracefully_*`` entries are stored as the *separator* of the
            current group and implicitly close it.
          - Everything else is a content entry.
        """
        groups: list[_ResetGroup] = []
        current = _ResetGroup()

        for entry in entries:
            if entry.kind != "PList":
                # Pat entries should not appear in a PLB, but handle gracefully
                current.content_entries.append(entry)
                continue

            name = entry.name

            if name.startswith("reset_"):
                # A reset starts a new group.  If the current group already has
                # content (or reset entries from a previous reset), save it first.
                if current.reset_entries or current.content_entries:
                    groups.append(current)
                    current = _ResetGroup()
                current.reset_entries.append(entry)

            elif (
                name.startswith("pre_precat_")
                or name.startswith("scn_preprecat_")
            ):
                current.precat_entries.append(entry)

            elif name.startswith("end_gracefully_"):
                current.separator = entry
                groups.append(current)
                current = _ResetGroup()

            else:
                current.content_entries.append(entry)

        # Don't forget the last group if it was never closed by end_gracefully
        if current.reset_entries or current.content_entries:
            groups.append(current)

        return groups

    # ── Default trimming ──────────────────────────────────────────────────────

    @staticmethod
    def _trim_default(
        entries:       list[PlistEntry],
        content_names: set[str],
    ) -> list[PlistEntry]:
        """Keep only entries whose name is in *content_names*."""
        return [e for e in entries if e.kind == "PList" and e.name in content_names]

    # ── Step 5: collect hotreset plists ───────────────────────────────────────

    def _collect_hotresets(self, content_blocks: list[PlistBlock]) -> list[PlistBlock]:
        """
        For *default* design: look up each content block's ``preburst`` name in
        the source file's block_map and return those blocks.

        If a referenced preburst block does not exist in the source file it is
        silently skipped.
        """
        result: list[PlistBlock] = []
        for cb in content_blocks:
            if cb.preburst and cb.preburst in self._file.block_map:
                result.append(self._file.block_map[cb.preburst])
        return result
