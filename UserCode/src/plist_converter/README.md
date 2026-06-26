# plist_converter

CLI tool that reads a `.plist` file, locates the specified PLB (main plist) blocks, and
converts the surrounding content plists between the two structural formats used in CWF
scan-pattern validation: **default** (standard) and **Chico**.

---

## Background — Two Plist Structures

### Default (standard) structure

Each content plist is independent: it holds only the actual test patterns and references
its hotreset via a `[PreBurstPList <hotreset_name>]` header attribute.  The hotreset
block (`scn_c_…_x_hotreset_…`) exists as a separate `GlobalPList` in the file, and the
PLB simply lists the content plists with no glue logic in its body.

```
GlobalPList scn_c_inf_f1_begin_sSs_edt_vinfraLBtd0_tatpg_ph1_list
    [PreBurstPList  scn_c_inf_x_hotreset_sSs_edt_vinfraLBtd0_tatpg_ph1_list]
    [PostBurstPList endgracefully_Mscn_…] {
   Pat <content patterns>;
}

GlobalPList scn_c_inf_x_hotreset_sSs_edt_vinfraLBtd0_tatpg_ph1_list {
   PList reset_…;
   PList scn_preprecat_…;
   Pat <safety-seal / hotreset patterns ending in _r0H…>;
}

GlobalPList scn_c_inf_f1_begin_sSs_edt_vinfraLB_tatpg_list {
   PList scn_c_inf_f1_begin_sSs_edt_vinfraLBtd0_tatpg_ph1_list;
   …
}
```

### Chico structure

The hotreset is merged into the content plist body (prefixed by a `gid_clear` pattern).
The PLB itself holds the `reset_*` / `scn_preprecat_*` / `end_gracefully_*` glue calls and
carries `[PostBurstPList …] [Flatten]` in its header.

```
GlobalPList scn_c_inf_f1_begin_sSs_edt_vinfraLBtd0_tatpg_ph1_list [Flatten] {
   Pat d71716…cwf_stf_gid_clear_rev0;          ← gid_clear (first)
   Pat <safety-seal / hotreset patterns>;
   Pat <hotreset boundary pattern  _r0Hph…>;   ← split point
   Pat <content patterns>;
}

GlobalPList scn_c_inf_f1_begin_sSs_edt_vinfraLB_tatpg_list
    [PostBurstPList endgracefully_Mscn_…] [Flatten] {
   PList reset_…;
   PList scn_preprecat_…;
   PList scn_c_inf_f1_begin_sSs_edt_vinfraLBtd0_tatpg_ph1_list;
   PList end_gracefully_…;
   …
}
```

---

## Conversion modes

| Mode | Direction | What it does |
|---|---|---|
| `chico-to-default` | Chico → Default | Splits each merged content block into a separate hotreset block + content block; strips glue entries from the PLB header and body |
| `default-to-chico` | Default → Chico | Merges each hotreset block into its content block (gid_clear prepended if found); adds reset/precat/end_gracefully glue to the PLB body and adds `[PostBurstPList] [Flatten]` to the PLB header |

---

## Usage

Run from the **repo root** (`Plist_Agent/`):

```
python UserCode/src/plist_converter/main.py [options]
```

### chico-to-default
``` 
python.exe .\UserCode\src\plist_converter\main.py --plist  "I:\hdmxpats\cwf\MscnCdXCC\RevTCB0.0\p29\plb\scan_uncore_class_xdcc_debug.plist"  --plbs "C:\Users\jdcubero\OneDrive - Intel Corporation\Documents\code\Plist_Agent\UserCode\src\plist_converter\data\names_top_die_n_cpufdi_missed_only_begin.list" --mode   chico-to-default --output "C:\Users\jdcubero\OneDrive - Intel Corporation\Documents\code\Plist_Agent\UserCode\src\plist_converter\data\top_die_n_cpufdi_missed_only_begin.plist"
```

### default-to-chico
```
python.exe .\UserCode\src\plist_converter\main.py --plist  "I:\hdmxpats\cwf\MscnCdXCC\RevTCB0.0\p32\plb\scan_uncore_class_xdcc_debug.plist"  --plbs "C:\Users\jdcubero\OneDrive - Intel Corporation\Documents\code\Plist_Agent\UserCode\src\plist_converter\data\names_top_die_n_cpufdi_missed_only_begin.list" --mode default-to-chico --output "C:\Users\jdcubero\OneDrive - Intel Corporation\Documents\code\Plist_Agent\UserCode\src\plist_converter\data\top_die_n_cpufdi_missed_only_begin_v3.plist"
```

### chico-to-default

```bash
python UserCode/src/plist_converter/main.py \
  --plist  "I:\hdmxpats\cwf\MscnCdXCC\RevTCB0.0\p30\plb\scan_uncore_class_xdcc_debug.plist" \
  --plbs   "UserCode\src\plist_converter\data\names_vinfraLB.list" \
  --mode   chico-to-default \
  --output "UserCode\src\plist_converter\data\vinfraLB_default.plist"
```

### default-to-chico (extraction)

```bash
python UserCode/src/plist_converter/main.py \
  --plist  "I:\hdmxpats\cwf\MscnCdXCC\RevTCB0.0\p30\plb\scan_uncore_class_xdcc_debug.plist" \
  --plbs   "UserCode\src\plist_converter\data\names_vinfraLB.list" \
  --mode   default-to-chico \
  --output "UserCode\src\plist_converter\data\vinfraLB_chico.plist"
```

> **PowerShell note:** always wrap paths that contain spaces in double quotes.

---

## CLI Reference

| Argument | Required | Description |
|---|---|---|
| `--plist PATH` | yes | Input `.plist` file (source of all `GlobalPList` blocks) |
| `--plbs FILE` | yes | Text file listing the PLB / main-plist names to process — one name per line. Blank lines and lines starting with `#` are ignored. |
| `--mode MODE` | yes | Conversion direction: `chico-to-default` or `default-to-chico` |
| `--output PATH` | yes | Output `.plist` file path |
| `--gid-clear PATTERN` | no | *(default-to-chico only)* Pattern name to insert as the first `Pat` entry in every merged content block. If omitted, the source plist is searched automatically; if still not found, a placeholder `Pat <gid_clear_pattern>;` is written for manual replacement. |

### `--plbs` file format

```
# vinfraLB PLBs
scn_c_inf_f1_begin_sSs_edt_vinfraLB_tatpg_list
scn_c_inf_f1_begin_sSs_edt_vinfraLB_atpg_list
```

---

## Lifecycle

```
main.py → AppRunner.run()
              ├── [1/5] setup()     ← argparse
              ├── [2/5] load plbs   ← read --plbs file
              ├── [3/5] extract     ← Parser → Extractor (locate PLB + content blocks)
              ├── [4/5] transform   ← Transformer (chico-to-default split logic)
              └── [5/5] write       ← Generator → output .plist
```

---

## `chico-to-default` transformation detail

For each content block (chico-style):

1. Remove the `cwf_stf_gid_clear` pattern (always the first `Pat` entry).
2. Find the **hotreset boundary**: scan entries from the bottom up; the first `Pat` whose
   name matches `_r\dH` (e.g. `_r0Hph1`) is the split point.
3. Derive the **hotreset block name** from the content block name:
   - Replace section 4 (frequency, e.g. `f1`) → `x`
   - Replace section 5 (flow, e.g. `begin`) → `hotreset`
   - Example: `scn_c_inf_f1_begin_sSs_edt_vinfraLBtd0_tatpg_ph1_list`
     → `scn_c_inf_x_hotreset_sSs_edt_vinfraLBtd0_tatpg_ph1_list`
4. Build the **hotreset block**: `reset_*` + `scn_preprecat_*` PList calls (taken from the
   PLB body, first pair only) prepended to all entries up to and including the `_r\dH` Pat.
5. Build the **new content block**: same name, header with
   `[PreBurstPList <hotreset>] [PostBurstPList <endgracefully>]`, body contains only the
   entries after the `_r\dH` boundary.

For the PLB:
- Remove all `reset_*`, `scn_preprecat_*`, `pre_precat_*`, and `end_gracefully_*` entries
  from the body.
- Strip `[PostBurstPList …]` and `[Flatten]` from the header.

---

## `default-to-chico` transformation detail

For each content block (default-style with `[PreBurstPList]` / `[PostBurstPList]`):

1. Look up the corresponding **hotreset block** via the `[PreBurstPList]` attribute.
2. Search the entire source plist for a `cwf_stf_gid_clear` Pat entry and prepend it
   (if not found, a warning is printed and the gid_clear is omitted).
3. Append all **Pat entries from the hotreset block** (PList `reset_*` / `scn_preprecat_*`
   calls in the hotreset block are skipped — they go to the PLB body instead).
4. Append all entries from the content block.
5. Build the merged block: same name, header `[Flatten]` only (no `[PreBurstPList]` /
   `[PostBurstPList]`).

For the PLB:
- Add `[PostBurstPList <endgracefully>]` and `[Flatten]` to the header (endgracefully name
  taken from the first content block’s `[PostBurstPList]` attribute).
- Prepend `reset_*` and `scn_preprecat_*` PList entries (from the first hotreset block).
- Append `end_gracefully_*` PList entry, derived from the endgracefully name by inserting an
  underscore: `endgracefully_X` → `end_gracefully_X`.

---

## Project structure

```
UserCode/src/plist_converter/
├── main.py              ← Entry point
├── data/                ← Input list files and output .plist files
├── config/              ← Reserved for future configuration
└── libs/
    ├── __init__.py
    ├── app_runner.py    ← CLI arg parsing + 5-step lifecycle
    ├── Extractor.py     ← Locates PLB + content blocks in the source plist
    ├── Transformer.py   ← Structural transformation (both directions)
    └── Generator.py     ← Writes output .plist (preserves #Pat commented entries)
```

---

## Authors

| Name | Role |
|---|---|
| | |
