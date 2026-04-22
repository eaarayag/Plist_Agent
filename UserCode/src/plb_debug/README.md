# PLB Debug Tool

## Overview

Command-line and GUI tool for generating PLB (Pattern List Block) debug files from `.plist` scan bundles. Supports wildcard/regex search, IO-equivalent search, and non-interactive batch mode for agent/automation integration.

## Requirements

- Python 3.10+
- Tkinter (bundled with standard Python installations)

## Setup

```bash
# Navigate to the project folder
cd UserCode/src/plb_debug

# No additional dependencies required — uses only the Python standard library.
```

## Usage

Run from the project root (`UserCode/src/plb_debug/`):

```bash
# GUI mode
python main.py --gui

# Interactive CLI mode (step-by-step prompts)
python main.py --interactive

# Non-interactive batch mode (agent/automation)
python main.py --plist scan_foo.plist --search "inf*atpg*ph1" --mode 1

# Multiple searches, no PreBurstPList
python main.py --plist scan_foo.plist \
    --search "inf*ph1" --mode 1 \
    --search "clk*reset" --mode 1 \
    --no-preburst
```

Search modes:
- `1` — Regex / wildcard (e.g. `inf*atpg*ph1`)
- `2` — IO equivalent IE (e.g. `scn_c_inf_x_begin_sEs_edt_IEvinfra1_atpg_list`)

The entry point delegates all logic to `AppRunner` via the lifecycle:

```
main.py  →  AppRunner.run()
                ├── setup()    # parse args
                ├── start()    # dispatch: GUI / interactive CLI / batch runner
                └── shutdown() # exit with status code
```

## Project Structure

```
plb_debug/
├── config/          # Project-specific configuration
│   └── users_config.json
├── data/            # Usage log and collaterals
│   └── Usage_Log.txt
├── libs/            # Internal modules — all application logic lives here
│   ├── __init__.py
│   ├── app_runner.py  # Lifecycle orchestrator + batch runner
│   ├── cli_app.py     # CLIApp adapter + interactive CLI flow
│   ├── Extractor.py   # PList entry extraction logic
│   ├── Finder.py      # Search/match mixin
│   ├── Generator.py   # Debug PList generation logic
│   ├── UsageLog.py    # Usage logging utilities
│   ├── Users.py       # User configuration management
│   └── GUI/
│       ├── __init__.py
│       ├── Main_GUI.py  # Tkinter GUI application
│       └── Aux_GUI.py   # GUI helper widgets (ToolTip, etc.)
├── main.py          # Thin entry point: parse args, run AppRunner
└── README.md        # This file
```

## Authors

| Name | Contact |
|---|---|
| lmarinbe | |

## Notes

- The `Config/` folder is now `config/` and `data/` per the standard project skeleton.
- `UsageLog.py` writes to `data/Usage_Log.txt`; `Users.py` reads `config/users_config.json`.
- The `.github/agents/plb_debug_agent.agent.md` VS Code Copilot agent is now at `agents/plb_debug_agent.agent.md`.
