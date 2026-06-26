"""
Transformer.py — Applies structural transformations between plist formats.

chico-to-default
----------------
For each content block (chico-style, [Flatten], gid_clear as first entry):
  1. Remove the gid_clear pattern.
  2. Find the hotreset boundary: scan from the bottom up for the first Pat whose
     name matches `_r\\dH` (e.g. _r0Hph1, _r0Hph2).  Everything from the top of
     the body up to and including that Pat is the hotreset portion; everything
     after it is the content portion.
  3. Derive the hotreset block name from the content block name by replacing
     section 4 (0-based index 3, frequency) with "x" and section 5 (0-based
     index 4, flow) with "hotreset".
  4. Build the hotreset block: reset + precat PList calls (from the PLB) prepended
     to the hotreset portion.
  5. Build the new content block: same name, header with
     [PreBurstPList <hotreset>] [PostBurstPList <endgracefully>].

For the PLB:
  - Remove all reset_* / scn_preprecat_* / pre_precat_* / end_gracefully_* entries
    from the body.
  - Strip [PostBurstPList ...] and [Flatten] from the header.

default-to-chico
----------------
For each content block (default-style, [PreBurstPList] / [PostBurstPList]):
  1. Locate the corresponding hotreset block via [PreBurstPList].
  2. Prepend a gid_clear Pat entry (searched in source plist; omitted if absent).
  3. Append the Pat entries from the hotreset block (skip PList reset_*/precat_*).
  4. Append all entries from the content block.
  5. Build merged block: same name, header with [Flatten] only.

For the PLB:
  - Add [PostBurstPList <endgracefully>] [Flatten] to the header.
  - Prepend reset_* and scn_preprecat_* PList entries (from the first hotreset block).
  - Append end_gracefully_* PList entry (derived from endgracefully_* name).

Public API
----------
    PlistTransformer : instantiate once.
        .chico_to_default(plb_blocks, content_blocks)
        .default_to_chico(plb_blocks, content_blocks, hotreset_blocks,
                          gid_clear_io=None, gid_clear_ie=None)
"""

from __future__ import annotations

import re

from src.plist_extractor.libs.Parser import PlistBlock, PlistEntry


# ─── Constants ────────────────────────────────────────────────────────────────

_RE_HOTRESET_PAT  = re.compile(r"_r\dH")
_RE_CONTENT_TYPE  = re.compile(r"5o([12])")
_GID_CLEAR_SUBSTR = "cwf_stf_gid_clear"


# ─── Block-type helpers ───────────────────────────────────────────────────────

def _detect_content_type(cb: PlistBlock, hr: PlistBlock | None) -> str:
    """
    Detect whether a content block belongs to the IO/sSs (5o2) or IE/sEs (5o1)
    family by scanning Pat entries for the '5o1' / '5o2' marker in the sixth
    section of the pattern name.

    Returns 'IO', 'IE', or 'unknown' (treated as IO).
    """
    sources = list(cb.entries)
    if hr is not None:
        sources.extend(hr.entries)
    for e in sources:
        if e.kind == "Pat":
            m = _RE_CONTENT_TYPE.search(e.name)
            if m:
                return "IO" if m.group(1) == "2" else "IE"
    return "unknown"


# ─── Name helpers ─────────────────────────────────────────────────────────────

def _is_reset_or_precat(name: str) -> bool:
    return (
        name.startswith("reset_")
        or name.startswith("pre_precat_")
        or name.startswith("scn_preprecat_")
    )


def _is_end_gracefully(name: str) -> bool:
    return name.startswith("end_gracefully_") or name.startswith("endgracefully_")


def _is_non_content(name: str) -> bool:
    return _is_reset_or_precat(name) or _is_end_gracefully(name)


def _derive_hotreset_name(content_name: str) -> str:
    """
    Derive the hotreset block name from a content plist name.

    Content plist name structure (1-indexed sections, split on "_"):
        scn_c_<domain>_<freq>_<flow>_<approach>_edt_<partition>_<type>_<phase>_list
         1   2    3      4      5       6         7       8         9     10     11

    Transformation (0-based indices):
        index 3  (section 4, frequency) → "x"
        index 4  (section 5, flow)      → "hotreset"

    Example:
        scn_c_inf_f1_begin_sSs_edt_vinfraLBtd0_tatpg_ph1_list
        → scn_c_inf_x_hotreset_sSs_edt_vinfraLBtd0_tatpg_ph1_list
    """
    parts = content_name.split("_")
    if len(parts) > 3:
        parts[3] = "x"
    if len(parts) > 4:
        parts[4] = "hotreset"
    return "_".join(parts)


# ─── PlistTransformer ─────────────────────────────────────────────────────────

class PlistTransformer:
    """
    Performs structural transformations on extracted plist blocks.

    Supports: chico-to-default and default-to-chico.
    """

    # ── Public ────────────────────────────────────────────────────────────────

    def chico_to_default(
        self,
        plb_blocks:     list[PlistBlock],
        content_blocks: list[PlistBlock],
    ) -> list[PlistBlock]:
        """
        Transform Chico-style blocks back to default (standard) plist structure.

        Parameters
        ----------
        plb_blocks:
            The main PLB blocks (one per requested PLB name).
        content_blocks:
            The chico-style content blocks referenced by those PLBs.

        Returns
        -------
        list[PlistBlock]
            Ordered: hotreset blocks → content blocks → PLB blocks.
        """
        content_by_name = {b.name: b for b in content_blocks}

        result_hotresets: list[PlistBlock] = []
        result_content:   list[PlistBlock] = []
        result_plbs:      list[PlistBlock] = []

        seen_hotresets: set[str] = set()
        seen_content:   set[str] = set()

        for plb in plb_blocks:
            # ── 1. Extract reset/precat entries from PLB (first pair only) ────
            reset_entry:  PlistEntry | None = None
            precat_entry: PlistEntry | None = None
            for e in plb.entries:
                if e.kind == "PList":
                    if reset_entry is None and e.name.startswith("reset_"):
                        reset_entry = e
                    if precat_entry is None and (
                        e.name.startswith("scn_preprecat_")
                        or e.name.startswith("pre_precat_")
                    ):
                        precat_entry = e
                if reset_entry and precat_entry:
                    break

            endgracefully_name = plb.postburst  # from [PostBurstPList ...]

            # ── 2. Process each content plist in PLB order ────────────────────
            for entry in plb.entries:
                if entry.kind != "PList" or _is_non_content(entry.name):
                    continue

                cb = content_by_name.get(entry.name)
                if cb is None:
                    print(f"  WARNING: Content block not found for splitting: '{entry.name}' — skipping.")
                    continue

                if cb.name in seen_content:
                    continue
                seen_content.add(cb.name)

                hotreset_name = _derive_hotreset_name(cb.name)
                hr_block, ct_block = self._split_content_block(
                    cb, hotreset_name, reset_entry, precat_entry, endgracefully_name
                )

                if hotreset_name not in seen_hotresets:
                    result_hotresets.append(hr_block)
                    seen_hotresets.add(hotreset_name)
                result_content.append(ct_block)

            # ── 3. Transform PLB ───────────────────────────────────────────────
            result_plbs.append(self._transform_plb(plb))

        return result_hotresets + result_content + result_plbs

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _split_content_block(
        cb:                 PlistBlock,
        hotreset_name:      str,
        reset_entry:        PlistEntry | None,
        precat_entry:       PlistEntry | None,
        endgracefully_name: str | None,
    ) -> tuple[PlistBlock, PlistBlock]:
        """
        Split a chico-style content block into (hotreset_block, content_block).

        Algorithm:
          1. Remove gid_clear pattern from entries.
          2. Scan from bottom to find the hotreset boundary Pat (name matches _r\\dH).
          3. Entries up to and including the boundary → hotreset body.
          4. Entries after the boundary → content body.
          5. Prepend reset + precat PList calls to the hotreset body.
          6. Build hotreset block (no header options).
          7. Build content block with [PreBurstPList <hr>] [PostBurstPList <end>].
        """
        # Remove gid_clear
        entries = [e for e in cb.entries if _GID_CLEAR_SUBSTR not in e.name]

        # Find hotreset boundary (scan from bottom)
        boundary_idx: int | None = None
        for i in range(len(entries) - 1, -1, -1):
            e = entries[i]
            if e.kind in ("Pat", "comment") and _RE_HOTRESET_PAT.search(e.name):
                boundary_idx = i
                break

        if boundary_idx is None:
            # No boundary found — treat all as hotreset content, content body empty
            print(
                f"  WARNING: No hotreset boundary pattern (_r\\dH) found in '{cb.name}'. "
                "All entries will go into the hotreset block."
            )
            hr_body = entries
            ct_body: list[PlistEntry] = []
        else:
            hr_body = entries[: boundary_idx + 1]
            ct_body = entries[boundary_idx + 1 :]

        # Build hotreset block entries: reset + precat first, then hr_body
        hr_entries: list[PlistEntry] = []
        if reset_entry is not None:
            hr_entries.append(reset_entry)
        if precat_entry is not None:
            hr_entries.append(precat_entry)
        hr_entries.extend(hr_body)

        hr_raw_header = f"GlobalPList {hotreset_name} {{\n"
        hr_block = PlistBlock(
            name        = hotreset_name,
            options_raw = "",
            preburst    = None,
            postburst   = None,
            entries     = hr_entries,
            raw_header  = hr_raw_header,
        )

        # Build content block
        options_parts = [f"[PreBurstPList {hotreset_name}]"]
        if endgracefully_name:
            options_parts.append(f"[PostBurstPList {endgracefully_name}]")
        options_raw = " ".join(options_parts)

        ct_raw_header = f"GlobalPList {cb.name} {options_raw} {{\n"
        ct_block = PlistBlock(
            name        = cb.name,
            options_raw = options_raw,
            preburst    = hotreset_name,
            postburst   = endgracefully_name,
            entries     = ct_body,
            raw_header  = ct_raw_header,
        )

        return hr_block, ct_block

    @staticmethod
    def _transform_plb(plb: PlistBlock) -> PlistBlock:
        """
        Return a transformed copy of the PLB for default structure:
          - Remove reset_* / precat_* / end_gracefully_* entries from body.
          - Strip [PostBurstPList ...] and [Flatten] from header.
        """
        new_entries = [
            e for e in plb.entries
            if not (e.kind == "PList" and _is_non_content(e.name))
        ]

        # Reconstruct a clean header (name only, no options)
        new_raw_header = f"GlobalPList {plb.name} {{\n"

        return PlistBlock(
            name        = plb.name,
            options_raw = "",
            preburst    = None,
            postburst   = None,
            entries     = new_entries,
            raw_header  = new_raw_header,
        )


    # ═══════════════════════════════════════════════════════════════════════════
    # default-to-chico
    # ═══════════════════════════════════════════════════════════════════════════

    def default_to_chico(
        self,
        plb_blocks:      list[PlistBlock],
        content_blocks:  list[PlistBlock],
        hotreset_blocks: list[PlistBlock],
        gid_clear_io:    PlistEntry | None = None,
        gid_clear_ie:    PlistEntry | None = None,
    ) -> list[PlistBlock]:
        """
        Transform default-style blocks into Chico-style plist structure.

        Parameters
        ----------
        plb_blocks:
            The main PLB blocks (one per requested PLB name).
        content_blocks:
            Default-style content blocks (have [PreBurstPList] / [PostBurstPList]).
        hotreset_blocks:
            Default-style hotreset blocks (separate blocks with reset_* PList entries
            and the hotreset Pat sequences).
        gid_clear_io:
            PlistEntry to prepend in IO/sSs/5o2 content blocks (first Pat entry).
        gid_clear_ie:
            PlistEntry to prepend in IE/sEs/5o1 content blocks (first Pat entry).
            For blocks where the type cannot be detected, gid_clear_io is used.

        Returns
        -------
        list[PlistBlock]
            Ordered: merged content blocks -> PLB blocks.
        """
        hotreset_by_name = {b.name: b for b in hotreset_blocks}
        content_by_name  = {b.name: b for b in content_blocks}

        result_content: list[PlistBlock] = []
        result_plbs:    list[PlistBlock] = []

        seen_content: set[str] = set()

        for plb in plb_blocks:
            # ── 1. Gather reset/precat/endgracefully from first content plist ──
            reset_entry:        PlistEntry | None = None
            precat_entry:       PlistEntry | None = None
            endgracefully_name: str | None        = None

            for entry in plb.entries:
                if entry.kind != "PList":
                    continue
                cb = content_by_name.get(entry.name)
                if cb is None:
                    continue
                if endgracefully_name is None:
                    endgracefully_name = cb.postburst
                if cb.preburst and reset_entry is None:
                    hr = hotreset_by_name.get(cb.preburst)
                    if hr is not None:
                        for e in hr.entries:
                            if e.kind == "PList":
                                if reset_entry is None and e.name.startswith("reset_"):
                                    reset_entry = e
                                if precat_entry is None and (
                                    e.name.startswith("scn_preprecat_")
                                    or e.name.startswith("pre_precat_")
                                ):
                                    precat_entry = e
                            if reset_entry and precat_entry:
                                break
                if reset_entry and precat_entry and endgracefully_name:
                    break

            # ── 2. Process each content plist in PLB order ────────────────────
            for entry in plb.entries:
                if entry.kind != "PList":
                    continue
                cb = content_by_name.get(entry.name)
                if cb is None:
                    continue
                if cb.name in seen_content:
                    continue
                seen_content.add(cb.name)

                hr = hotreset_by_name.get(cb.preburst) if cb.preburst else None
                content_type  = _detect_content_type(cb, hr)
                gid_clear     = gid_clear_ie if content_type == "IE" else gid_clear_io
                merged = self._merge_content_block(cb, hr, gid_clear)
                result_content.append(merged)

            # ── 3. Transform PLB ───────────────────────────────────────────────
            result_plbs.append(
                self._transform_plb_to_chico(
                    plb, reset_entry, precat_entry, endgracefully_name
                )
            )

        return result_content + result_plbs

    @staticmethod
    def _merge_content_block(
        cb:              PlistBlock,
        hr:              PlistBlock | None,
        gid_clear_entry: PlistEntry | None,
    ) -> PlistBlock:
        """
        Merge a default-style content block with its hotreset block into a
        Chico-style flat content block.

        Output structure:
            GlobalPList <name> [Flatten] {
               Pat gid_clear;              <- if found in source plist
               Pat <hotreset patterns>;    <- Pat/comment entries from hotreset block
               Pat <content patterns>;     <- all entries from content block
            }
        """
        merged: list[PlistEntry] = []

        if gid_clear_entry is not None:
            merged.append(gid_clear_entry)

        # Pat/comment entries from hotreset block (skip PList reset_*/precat_* calls)
        if hr is not None:
            for e in hr.entries:
                if e.kind in ("Pat", "comment"):
                    merged.append(e)

        # All entries from content block
        merged.extend(cb.entries)

        new_raw_header = f"GlobalPList {cb.name} [Flatten] {{\n"
        return PlistBlock(
            name        = cb.name,
            options_raw = "[Flatten]",
            preburst    = None,
            postburst   = None,
            entries     = merged,
            raw_header  = new_raw_header,
        )

    @staticmethod
    def _transform_plb_to_chico(
        plb:                PlistBlock,
        reset_entry:        PlistEntry | None,
        precat_entry:       PlistEntry | None,
        endgracefully_name: str | None,
    ) -> PlistBlock:
        """
        Transform a default-style PLB into a Chico-style PLB:
          - Add [PostBurstPList <endgracefully>] [Flatten] to the header.
          - Prepend reset_* and scn_preprecat_* PList entries to the body.
          - Append end_gracefully_* PList entry to the body.

        end_gracefully_* is derived from endgracefully_* by inserting an
        underscore: "endgracefully_X" -> "end_gracefully_X".
        """
        # Derive end_gracefully_* from endgracefully_*
        end_gracefully_name: str | None = None
        if endgracefully_name and endgracefully_name.startswith("endgracefully_"):
            end_gracefully_name = (
                "end_gracefully_" + endgracefully_name[len("endgracefully_"):]
            )

        new_entries: list[PlistEntry] = []
        if reset_entry is not None:
            new_entries.append(reset_entry)
        if precat_entry is not None:
            new_entries.append(precat_entry)
        new_entries.extend(plb.entries)
        if end_gracefully_name:
            new_entries.append(
                PlistEntry(
                    kind = "PList",
                    name = end_gracefully_name,
                    raw  = f"   PList {end_gracefully_name};\n",
                )
            )

        options_parts = []
        if endgracefully_name:
            options_parts.append(f"[PostBurstPList {endgracefully_name}]")
        options_parts.append("[Flatten]")
        options_raw = " ".join(options_parts)

        new_raw_header = f"GlobalPList {plb.name} {options_raw} {{\n"
        return PlistBlock(
            name        = plb.name,
            options_raw = options_raw,
            preburst    = None,
            postburst   = endgracefully_name,
            entries     = new_entries,
            raw_header  = new_raw_header,
        )
