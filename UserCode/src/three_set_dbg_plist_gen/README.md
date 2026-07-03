# Three Set Debug Plist Generator

## Overview

Reads a `.plist` file and generates **three** copies of every selected debug PLB chain by:

1. **Renaming** the partition field (token 8, 0-indexed token 7) in every plist name with a directional suffix.
2. **Replacing** the precat `PList` entry inside the hotreset block (standard structure) or PLB body (chico structure) with a single directional precat.

| Suffix | Direction | Precat (base variant)                              |
|--------|-----------|-----------------------------------------------------|
| UU3    | nor       | `pre_precat_Mscn_stf400_Cdie_STF_grdt_nor_uncore`  |
| UU4    | mid       | `pre_precat_Mscn_stf400_Cdie_STF_grdt_mid_uncore`  |
| UU5    | sou       | `pre_precat_Mscn_stf400_Cdie_STF_grdt_sou_uncore`  |

The same logic applies to the `top` precat variant, appending `_top` to each name above.

---

## Requirements

- Python 3.10+

---

## Usage

```bash
# Process all sSs/IO/5o2 PLBs found in the file:
python main.py -i <input.plist>

# Process only the PLBs listed in a .list file:
python main.py -i <input.plist> -m selected -l <plb_names.list>

# Process all sSs/IO/5o2 PLBs EXCEPT those listed in a .list file:
python main.py -i <input.plist> -m exclude -l <exclude_names.list>

# Specify output location (directory or file prefix):
python main.py -i <input.plist> -o <output_prefix>
python main.py -i <input.plist> -o <output_dir>/
```

```
python.exe .\UserCode\src\three_set_dbg_plist_gen\main.py -i "M:\cwf\a0\cwf\plists\workarea\b0.0p31_HVM\plist_per_die_script\clean_scan_uncore_class_xdcc_debug.plist" -o ".\UserCode\src\three_set_dbg_plist_gen\data\p32_scan_uncore_class_xdcc_debug" -m exclude -l ".\UserCode\src\three_set_dbg_plist_gen\data\plb_for_exclude.list"
```


### Full example commands

```bash
# All mode — process every detected PLB, output next to input file:
python main.py -i M:\scan_uncore_debug.plist

# Selected mode — only the two PLBs in my_plbs.list:
python main.py -i M:\scan_uncore_debug.plist -m selected -l data\my_plbs.list -o M:\out\three_set

# Exclude mode — all detected PLBs except those in skip.list, write to a folder:
python main.py -i M:\scan_uncore_debug.plist -m exclude -l data\skip.list -o M:\out\
```

### Arguments

| Argument | Short | Required | Description |
|---|---|---|---|
| `--input`  | `-i` | Yes | Input `.plist` file |
| `--mode`   | `-m` | No  | `all` (default), `selected`, or `exclude` — see modes below |
| `--list`   | `-l` | Conditional | `.list` file with PLB names — required when `--mode=selected` or `--mode=exclude` |
| `--output` | `-o` | No  | Output file prefix or directory (default: same dir as input, stem + `_three_set`) |

### Modes

| Mode | Behaviour | `--list` |
|---|---|---|
| `all` | Process every sSs/IO/5o2 PLB found in the file | Not used |
| `selected` | Process **only** the PLBs whose names appear in `--list` | Required |
| `exclude` | Process all sSs/IO/5o2 PLBs **except** those listed in `--list` | Required |

### `.list` file format

One full PLB name per line. Lines starting with `#` are ignored.

```
# My selected / excluded PLBs
scn_c_cfc_f1_begin_sSs_edt_cpuallc1r5_tatpg_list
scn_c_inf_f1_begin_sSs_edt_vinfraLBtd0_tatpg_list
```

---

## Output

Three files are created after each run:

| File | Contents |
|---|---|
| `<prefix>.plist` | All generated UU3/UU4/UU5 plist blocks, ordered: hotreset → content → PLB |
| `<prefix>_used_plists.list` | Three-section report listing the original PLBs, content plists, and hotreset plists used as sources |
| `<prefix>.log` | Full console log including a summary of processed/skipped PLBs and any warnings |

Duplicate `GlobalPList` declarations (same block referenced by multiple PLBs) are automatically suppressed — each block is written only once.

---

## Plist structure support

| Structure | PLB body | Hotreset | Precat location | Supported |
|---|---|---|---|---|
| Standard / Default | Content plist calls only | Separate block via `[PreBurstPList]` | Inside hotreset | ✓ |
| Chico              | Reset + precat + content + end_gracefully | Merged into content | Inside PLB body | ✓ |

**Note:** `[PostBurstPList end_gracefully_*]` references are **never** modified.

---

## Project structure

```
three_set_dbg_plist_gen/
├── main.py               Entry point (argparse -> AppRunner)
├── config/               (reserved for future configuration)
├── data/                 (place input .plist / .list files here if desired)
└── libs/
    ├── __init__.py
    ├── Parser.py         Tokenizes .plist files -> PlistFile / PlistBlock / PlistEntry
    ├── Extractor.py      Identifies PLBs (all/selected/exclude), classifies structure, extracts chains
    ├── Transformer.py    Generates UU3/UU4/UU5 renamed copies of each chain
    ├── Generator.py      Writes output .plist and report .list files
    └── app_runner.py     Orchestrates the pipeline (setup -> start -> shutdown) with logging
```

---

## Authors

| Name | Role |
|---|---|
| — | — |
