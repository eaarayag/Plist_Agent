"""
Transformer.py — Generates UU3/UU4/UU5 variant copies of a PLB chain.

For every PLB chain (standard or chico), three copies are produced:
    UU3 -> nor   (northern uncore)
    UU4 -> mid   (middle uncore)
    UU5 -> sou   (southern uncore)

The transformation rules differ by structure:

Standard structure (separate hotreset plist):
    - PLB        : rename token[7] with suffix; rename content-plist PList entries.
    - Content    : rename token[7] with suffix; update [PreBurstPList] ref.
    - Hotreset   : rename token[7] with suffix; replace precat PList entry.

Chico structure (precat lives in PLB body, no separate hotreset):
    - PLB        : rename token[7] with suffix; replace precat PList entry;
                   rename content-plist PList entries.
    - Content    : rename token[7] with suffix; body unchanged.

Rules that apply to BOTH structures:
    - reset_* / end_gracefully_* / endgracefully_* entries are NEVER renamed.
    - [PostBurstPList ...] in any header is NEVER modified.

Public API
----------
    PRECAT_MAP    : The precat replacement table (base/top × nor/mid/sou).
    rename_token7 : Utility to append a suffix to token[7] of a plist name.
    PlistSplitter : Main class; call .generate_variants(chain) → list[list[PlistBlock]].
"""

from __future__ import annotations

import re

from libs.Parser import PlistBlock, PlistEntry
from libs.Extractor import ChainData


# ─── Constants ────────────────────────────────────────────────────────────────

PRECAT_MAP: dict[str, dict[str, str]] = {
    "base": {
        "nor": "pre_precat_Mscn_stf400_Cdie_STF_grdt_nor_uncore",
        "mid": "pre_precat_Mscn_stf400_Cdie_STF_grdt_mid_uncore",
        "sou": "pre_precat_Mscn_stf400_Cdie_STF_grdt_sou_uncore",
    },
    "top": {
        "nor": "pre_precat_Mscn_stf400_Cdie_STF_grdt_nor_uncore_top",
        "mid": "pre_precat_Mscn_stf400_Cdie_STF_grdt_mid_uncore_top",
        "sou": "pre_precat_Mscn_stf400_Cdie_STF_grdt_sou_uncore_top",
    },
}

# Ordered variant definitions: (name_suffix, precat_key)
_VARIANTS: list[tuple[str, str]] = [
    ("UU3", "nor"),
    ("UU4", "mid"),
    ("UU5", "sou"),
]

# Known precat source names that get replaced
_PRECAT_SOURCES: frozenset[str] = frozenset({
    "scn_preprecat_cdie_grdt_base_sSs_list",
    "scn_preprecat_cdie_grdt_top_sSs_list",
})

_RE_PREBURST = re.compile(r"\[PreBurstPList\s+(\S+)\]")

_INDENT = "   "


# ─── Name helpers ─────────────────────────────────────────────────────────────

def rename_token7(name: str, suffix: str) -> str:
    """
    Append *suffix* to token[7] (0-indexed, the 8th underscore-separated field)
    of a plist name and return the modified name.

    Example::

        rename_token7("scn_c_cfc_f1_begin_sSs_edt_cpuallc1r5_tatpg_ph1_list", "UU3")
        -> "scn_c_cfc_f1_begin_sSs_edt_cpuallc1r5UU3_tatpg_ph1_list"

    If the name has fewer than 8 tokens the suffix is appended to the last token
    (graceful degradation — should not occur for well-formed plist names).
    """
    parts = name.split("_")
    idx = min(7, len(parts) - 1)
    parts[idx] = parts[idx] + suffix
    return "_".join(parts)


def get_precat_name(variant: str, nor_mid_sou: str) -> str:
    """Return the single precat name for *variant* (``"base"``/``"top"``) and direction."""
    return PRECAT_MAP[variant][nor_mid_sou]


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _is_infrastructure(name: str) -> bool:
    """
    Return True if *name* is an infrastructure entry that must NOT be renamed:
    reset_*, end_gracefully_*, endgracefully_*, pre_precat_*, scn_preprecat_*.
    """
    return (
        name.startswith("reset_")
        or name.startswith("end_gracefully_")
        or name.startswith("endgracefully_")
        or name.startswith("pre_precat_")
        or name.startswith("scn_preprecat_")
    )


def _copy_entry(e: PlistEntry) -> PlistEntry:
    return PlistEntry(kind=e.kind, name=e.name, raw=e.raw)


def _make_plist_entry(name: str) -> PlistEntry:
    return PlistEntry(kind="PList", name=name, raw=f"{_INDENT}PList {name};\n")


def _rebuild_header(block_name: str, options_raw: str, new_preburst: str | None) -> str:
    """
    Build a raw_header string for a renamed block.

    If *new_preburst* is provided, the ``[PreBurstPList ...]`` clause in
    *options_raw* is updated; all other clauses (PostBurstPList, Flatten, etc.)
    are kept verbatim.

    The [PostBurstPList ...] value is NEVER modified.
    """
    opts = options_raw
    if new_preburst is not None:
        opts = _RE_PREBURST.sub(f"[PreBurstPList {new_preburst}]", opts)

    opts = opts.strip()
    if opts:
        return f"GlobalPList {block_name} {opts} {{\n"
    return f"GlobalPList {block_name} {{\n"


# ─── PlistSplitter ────────────────────────────────────────────────────────────

class PlistSplitter:
    """
    Generates the three U3/U4/U5 variant sets for a given :class:`~libs.Extractor.ChainData`.

    Usage::

        splitter = PlistSplitter()
        variant_sets = splitter.generate_variants(chain)
        # variant_sets[0] → U3 blocks, [1] → U4, [2] → U5
    """

    def generate_variants(self, chain: ChainData) -> list[list[PlistBlock]]:
        """
        Produce three lists of :class:`~libs.Parser.PlistBlock`, one per variant.

        Each inner list is ordered:
            - Standard: hotreset blocks → content blocks → PLB block
            - Chico:    content blocks → PLB block

        Returns
        -------
        list[list[PlistBlock]]
            ``[U3_blocks, U4_blocks, U5_blocks]``
        """
        result: list[list[PlistBlock]] = []
        for suffix, nor_mid_sou in _VARIANTS:
            if chain.structure == "standard":
                blocks = self._transform_standard(chain, suffix, nor_mid_sou)
            else:
                blocks = self._transform_chico(chain, suffix, nor_mid_sou)
            result.append(blocks)
        return result

    # ── Standard ──────────────────────────────────────────────────────────────

    def _transform_standard(
        self,
        chain: ChainData,
        suffix: str,
        nor_mid_sou: str,
    ) -> list[PlistBlock]:
        """
        Build the renamed U{x} blocks for a standard-structure chain.

        Order: hotreset blocks → content blocks → PLB block.
        """
        new_precat_name = get_precat_name(chain.precat_variant, nor_mid_sou)

        # ── 1. Build renamed hotreset blocks ──────────────────────────────────
        # Maps original hotreset name → new hotreset name (needed for content updates)
        hotreset_name_map: dict[str, str] = {}
        new_hotresets: list[PlistBlock] = []

        for hr in chain.hotreset_plists:
            new_hr_name = rename_token7(hr.name, suffix)
            hotreset_name_map[hr.name] = new_hr_name

            new_entries: list[PlistEntry] = []
            for entry in hr.entries:
                if entry.kind == "PList" and entry.name in _PRECAT_SOURCES:
                    # Replace with the single directional precat
                    new_entries.append(_make_plist_entry(new_precat_name))
                else:
                    new_entries.append(_copy_entry(entry))

            new_hotresets.append(PlistBlock(
                name        = new_hr_name,
                options_raw = hr.options_raw,
                preburst    = None,
                postburst   = None,
                entries     = new_entries,
                raw_header  = _rebuild_header(new_hr_name, hr.options_raw, None),
            ))

        # ── 2. Build renamed content plist blocks ─────────────────────────────
        new_content: list[PlistBlock] = []

        for cb in chain.content_plists:
            new_cb_name = rename_token7(cb.name, suffix)
            new_preburst = (
                hotreset_name_map.get(cb.preburst)
                if cb.preburst
                else None
            )

            new_entries = [_copy_entry(e) for e in cb.entries]

            new_content.append(PlistBlock(
                name        = new_cb_name,
                options_raw = cb.options_raw,   # updated via _rebuild_header
                preburst    = new_preburst,
                postburst   = cb.postburst,     # PostBurstPList unchanged
                entries     = new_entries,
                raw_header  = _rebuild_header(new_cb_name, cb.options_raw, new_preburst),
            ))

        # ── 3. Build renamed PLB block ─────────────────────────────────────────
        new_plb_name = rename_token7(chain.plb.name, suffix)
        new_plb_entries: list[PlistEntry] = []

        for entry in chain.plb.entries:
            if entry.kind == "PList" and not _is_infrastructure(entry.name):
                new_entry_name = rename_token7(entry.name, suffix)
                new_plb_entries.append(_make_plist_entry(new_entry_name))
            else:
                new_plb_entries.append(_copy_entry(entry))

        new_plb = PlistBlock(
            name        = new_plb_name,
            options_raw = chain.plb.options_raw,
            preburst    = chain.plb.preburst,
            postburst   = chain.plb.postburst,
            entries     = new_plb_entries,
            raw_header  = _rebuild_header(new_plb_name, chain.plb.options_raw, None),
        )

        return new_hotresets + new_content + [new_plb]

    # ── Chico ─────────────────────────────────────────────────────────────────

    def _transform_chico(
        self,
        chain: ChainData,
        suffix: str,
        nor_mid_sou: str,
    ) -> list[PlistBlock]:
        """
        Build the renamed U{x} blocks for a chico-structure chain.

        Order: content blocks → PLB block.
        """
        new_precat_name = get_precat_name(chain.precat_variant, nor_mid_sou)

        # ── 1. Rename content plist blocks (body unchanged) ───────────────────
        new_content: list[PlistBlock] = []
        for cb in chain.content_plists:
            new_cb_name = rename_token7(cb.name, suffix)
            new_entries = [_copy_entry(e) for e in cb.entries]

            new_content.append(PlistBlock(
                name        = new_cb_name,
                options_raw = cb.options_raw,
                preburst    = cb.preburst,
                postburst   = cb.postburst,
                entries     = new_entries,
                raw_header  = _rebuild_header(new_cb_name, cb.options_raw, None),
            ))

        # ── 2. Build renamed PLB block ─────────────────────────────────────────
        new_plb_name = rename_token7(chain.plb.name, suffix)
        new_plb_entries: list[PlistEntry] = []

        for entry in chain.plb.entries:
            if entry.kind != "PList":
                new_plb_entries.append(_copy_entry(entry))
                continue

            name = entry.name

            if name in _PRECAT_SOURCES:
                # Replace with single directional precat
                new_plb_entries.append(_make_plist_entry(new_precat_name))

            elif _is_infrastructure(name):
                # reset_* / end_gracefully_* / pre_precat_* (other) → keep unchanged
                new_plb_entries.append(_copy_entry(entry))

            else:
                # Content plist reference → rename
                new_entry_name = rename_token7(name, suffix)
                new_plb_entries.append(_make_plist_entry(new_entry_name))

        new_plb = PlistBlock(
            name        = new_plb_name,
            options_raw = chain.plb.options_raw,
            preburst    = chain.plb.preburst,
            postburst   = chain.plb.postburst,
            entries     = new_plb_entries,
            raw_header  = _rebuild_header(new_plb_name, chain.plb.options_raw, None),
        )

        return new_content + [new_plb]
