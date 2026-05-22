"""
Matcher.py — Matches GlobalPList names against user-supplied filter criteria.

Public API
----------
    PlistMatcher : Configurable matcher built from CLI / interactive arguments.
                   Call matcher.matches(plist_name) -> bool.

Content-plist name convention (1-indexed, split on "_"):
    Section  1  : "scn"
    Section  2  : "c"
    Section  3  : power domain   (cfc, inf, ddr, …)
    Section  4  : frequency      (f1, f2, f3, f4, x, …)
    Section  5  : flow           (chk, srh, vmax, …)
    Section  6  : approach       (sSs, sEs, sEx, …)
    Section  7  : "edt"
    Section  8  : partition      (cpuall, ddrmc, fivrsshdc12, …)
    Section  9  : content type   (atpg, tatpg, chain, ca1tf, ca2tf, atpgtopRAM, …)
    Section 10  : phase          (ph1, ph2, …)  — may carry a topoff flavour suffix
    Section 11  : "list"

    (0-based index = section number − 1)

Full-content expansion (--full-content flag):
    "atpg"  -> {atpg, ca1tf}  +  regex  atpgtop\\w+
    "tatpg" -> {tatpg, ca2tf} +  regex  tatpgtop\\w+
    "chain" -> {chain}        +  regex  chaintop\\w+
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# ─── Constants ────────────────────────────────────────────────────────────────

# Minimum number of "_"-separated sections a valid content-plist name must have.
_MIN_SECTIONS = 11

# Phase tokens always start with "ph" followed by a digit (ph1, ph2, ph1topRAM, …).
# This distinguishes content plists from PLBs whose section-9 token is something
# else entirely (e.g. "repair", "begin", …).
_RE_PHASE_TOKEN = re.compile(r'^ph\d')

# Section indices (0-based)
_IDX_PREFIX       = 0   # "scn"
_IDX_POWER_DOMAIN = 2
_IDX_FREQUENCY    = 3
_IDX_FLOW         = 4
_IDX_APPROACH     = 5
_IDX_PARTITION    = 7
_IDX_CONTENT_TYPE = 8
_IDX_PHASE        = 9
_IDX_SUFFIX       = 10  # "list"


# ─── Helper ───────────────────────────────────────────────────────────────────

@dataclass
class _ExpandedTypes:
    """Pre-compiled content-type matching rules produced by :meth:`PlistMatcher._build_type_rules`."""
    exact:   frozenset[str]          # exact string matches
    regexes: list[re.Pattern]        # compiled regex patterns for topoff / wildcard variants


# ─── PlistMatcher ─────────────────────────────────────────────────────────────

class PlistMatcher:
    """
    Decides whether a ``GlobalPList`` name corresponds to a *content plist* that
    satisfies all active filter criteria.

    All filters are optional except *partitions*, which is always required.
    An omitted filter matches any value in that position.

    Parameters
    ----------
    partitions:
        One or more partition names (exact, case-sensitive).
    content_types:
        One or more content-type tokens.  When ``full_content`` is True these are
        automatically expanded with cell-aware and topoff variants.
    approach:
        Approach token filter (e.g. ``"sSs"``).  ``None`` = any.
    phase:
        Phase filter (e.g. ``"ph1"``).  Matched as a *prefix* of section 10 to
        tolerate topoff-flavour suffixes such as ``ph1topRAM``.  ``None`` = any.
    power_domain:
        Power-domain filter (e.g. ``"cfc"``).  ``None`` = any.
    frequency:
        Frequency filter (e.g. ``"f1"``).  ``None`` = any.
    flow:
        Flow filter (e.g. ``"vmax"``).  ``None`` = any.
    full_content:
        When True, each base content type is expanded to include cell-aware and
        topoff variants.
    skip_patterns:
        A list of substring patterns.  Any matched name that contains one of these
        substrings is excluded (applied as a post-filter).
    """

    def __init__(
        self,
        partitions:    list[str],
        content_types: list[str] | None = None,
        approach:      str | None       = None,
        phase:         str | None       = None,
        power_domain:  str | None       = None,
        frequency:     str | None       = None,
        flow:          str | None       = None,
        full_content:  bool             = False,
        skip_patterns: list[str] | None = None,
    ) -> None:
        if not partitions:
            raise ValueError("At least one partition must be specified.")

        self._partitions    = frozenset(partitions)
        self._approach      = approach
        self._phase         = phase
        self._power_domain  = power_domain
        self._frequency     = frequency
        self._flow          = flow
        self._skip_patterns = list(skip_patterns or [])

        # Build the type-matching rules
        self._type_rules: _ExpandedTypes | None = None
        if content_types:
            self._type_rules = self._build_type_rules(content_types, full_content)

    # ── Public interface ──────────────────────────────────────────────────────

    def matches(self, plist_name: str) -> bool:
        """
        Return True if *plist_name* is a content plist that satisfies all filters
        and is not excluded by any skip pattern.

        The name must:
          - contain at least ``_MIN_SECTIONS`` "_"-separated sections,
          - start with ``"scn"`` in section 1,
          - end with ``"list"`` in the last significant section.
        """
        parts = plist_name.split("_")

        # ── Structural validation ─────────────────────────────────────────────
        if len(parts) < _MIN_SECTIONS:
            return False
        if parts[_IDX_PREFIX] != "scn":
            return False
        if parts[-1] != "list":
            return False
        # Exclude hotreset plists — they share the partition/content-type sections
        # with content plists but are structural helpers, not content.
        if "_hotreset_" in plist_name:
            return False

        # Phase-section guard: content plists always have ph\d+ at section index 9.
        # PLBs use a non-phase token there (e.g. "repair"), so this rejects them.
        if not _RE_PHASE_TOKEN.match(parts[_IDX_PHASE]):
            return False

        # ── Positive filters (all must match) ─────────────────────────────────
        # Partition: startswith match so that instance suffixes are included.
        # e.g. partition="ddrmc" matches "ddrmcs0c0", "ddrmcs1c9", etc.
        # Use --skip to exclude unintended prefix matches (e.g. "ddrmcnor").
        if not any(parts[_IDX_PARTITION].startswith(p) for p in self._partitions):
            return False

        if self._power_domain and parts[_IDX_POWER_DOMAIN] != self._power_domain:
            return False

        if self._frequency and parts[_IDX_FREQUENCY] != self._frequency:
            return False

        if self._flow and parts[_IDX_FLOW] != self._flow:
            return False

        if self._approach and parts[_IDX_APPROACH] != self._approach:
            return False

        # Phase: use startswith to tolerate topoff-flavour suffixes (e.g. "ph1topRAM")
        if self._phase and not parts[_IDX_PHASE].startswith(self._phase):
            return False

        # Content type
        if self._type_rules is not None:
            ct = parts[_IDX_CONTENT_TYPE]
            if not self._content_type_matches(ct, self._type_rules):
                return False

        # ── Negative filters (skip patterns) ──────────────────────────────────
        if self._is_skipped(plist_name):
            return False

        return True

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _is_skipped(self, name: str) -> bool:
        """Return True if *name* contains any of the configured skip patterns."""
        return any(pat in name for pat in self._skip_patterns)

    @staticmethod
    def _content_type_matches(ct: str, rules: _ExpandedTypes) -> bool:
        """Return True if *ct* satisfies the expanded type rules."""
        if ct in rules.exact:
            return True
        return any(rx.fullmatch(ct) for rx in rules.regexes)

    @staticmethod
    def _build_type_rules(content_types: list[str], full_content: bool) -> _ExpandedTypes:
        """
        Build exact-match set and compiled regex list for the given *content_types*.

        When *full_content* is True the following expansions are applied:

        =========  ==============================  ===========================
        Base type  Additional exact types          Additional regex pattern
        =========  ==============================  ===========================
        atpg       ca1tf                           ``atpgtop\\w+``
        tatpg      ca2tf                           ``tatpgtop\\w+``
        chain       —                              ``chaintop\\w+``
        =========  ==============================  ===========================
        """
        exact:   set[str]          = set()
        regexes: list[re.Pattern]  = []

        for ct in content_types:
            ct_lower = ct.strip()
            exact.add(ct_lower)

            if full_content:
                if ct_lower == "atpg":
                    exact.add("ca1tf")
                    regexes.append(re.compile(r"atpgtop\w+"))
                elif ct_lower == "tatpg":
                    exact.add("ca2tf")
                    regexes.append(re.compile(r"tatpgtop\w+"))
                elif ct_lower == "chain":
                    regexes.append(re.compile(r"chaintop\w+"))

        return _ExpandedTypes(exact=frozenset(exact), regexes=regexes)
