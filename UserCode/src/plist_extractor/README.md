# plist_extractor

CLI tool that reads a `.plist` file, matches `GlobalPList` content blocks against user-supplied
filter criteria (partition, content type, approach, phase, etc.), collects the full call tree
(content plists → PLB → hotreset plists), trims multi-partition PLBs to only the requested
partition(s), and writes a clean output `.plist` file with `Version 5.0;` as the first line.

## Usage

### Batch mode
```
python main.py \
  --plist  <path/to/input.plist> \
  --partition <partition> [<partition> ...] \
  --output <path/to/output.plist> \
  [--content-type <type> [<type> ...]] \
  [--approach  <sSs|sEs|...>] \
  [--phase     <ph1|ph2|...>] \
  [--power-domain <cfc|inf|ddr|...>] \
  [--frequency    <f1|f2|...>] \
  [--flow         <chk|srh|vmax|...>] \
  [--full-content] \
  [--skip <pattern> [--skip <pattern> ...]]
```

### Interactive mode
```
python main.py --interactive
```

## Arguments

| Argument | Description |
|---|---|
| `--plist` | Input `.plist` file path (required) |
| `--partition` | One or more partition names to extract (required) |
| `--output` | Output `.plist` file path (required) |
| `--content-type` | Content types to match (`atpg`, `tatpg`, `chain`, `ca1tf`, `ca2tf`, `atpgtopRAM`, …). If omitted, all types are included. |
| `--approach` | Approach filter (e.g. `sSs`, `sEs`). If omitted, all approaches are included. |
| `--phase` | Phase filter (e.g. `ph1`, `ph2`). If omitted, all phases are included. |
| `--power-domain` | Power-domain filter (e.g. `cfc`, `inf`, `ddr`). Optional. |
| `--frequency` | Frequency filter (e.g. `f1`, `f2`). Optional. |
| `--flow` | Flow filter (e.g. `chk`, `srh`, `vmax`). Optional. |
| `--full-content` | Auto-expand a base content type: `atpg` → adds `ca1tf` + `atpgtop*`; `tatpg` → adds `ca2tf` + `tatpgtop*`; `chain` → adds `chaintop*` |
| `--skip` | Exclude any matched plist whose name contains this substring. Repeatable. |
| `--interactive` | Launch 8-step interactive guided flow. |

## Lifecycle

```
main.py → AppRunner.run()
              ├── setup()    ← argparse / interactive prompts
              ├── start()    ← Parser → Matcher → Extractor → Generator
              └── shutdown() ← sys.exit(code)
```

## Authors

| Name | Role |
|---|---|
| | |
