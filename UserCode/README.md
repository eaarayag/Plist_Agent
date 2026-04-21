# UserCode — Project Skeleton

This folder defines the **standard skeleton** for every application in this repository (console apps, agents, and tools).

## Structure

```
<UserCode>/
├── config/          # Shared configuration across all projects (env vars, common settings)
│   └── README.md
├── data/            # Shared collaterals reused across projects (JSON, CSV, XML, etc.)
│   └── README.md
├── src/
│   └── <project_name>/   # One folder per project — this is the only part added per new project
│       ├── config/       # Project-specific configuration
│       │   └── README.md
│       ├── data/         # Project-specific collaterals (JSON, CSV, XML, etc.)
│       │   └── README.md
│       ├── libs/         # Internal modules and helper libraries
│       │   ├── __init__.py
│       │   ├── app_runner.py  # Lifecycle: setup() → start() → shutdown()
│       │   └── README.md
│       ├── main.py       # Thin entry point: parse args, run AppRunner
│       └── README.md     # Project-level documentation
├── utilities/       # Shared utility scripts, classes, and data structures
│   └── README.md
└── README.md        # Top-level documentation (this file)
```

> `config/`, `data/`, and `utilities/` are created **once** and shared. Only a new `src/<project_name>/` folder is added for each new project.

## How to Use This Template

`config/` and `utilities/` are **shared** folders — they exist once per `UserCode` and are reused by all projects. **Do not copy them per project.**

When adding a new project, only create a new folder inside `src/`:

1. Copy `src/project_name/` and rename it to your project name (`snake_case`).
2. Fill in `src/<project_name>/README.md` with project-specific details.
3. Add project-specific config under `src/<project_name>/config/`.
4. Place project-specific modules under `src/<project_name>/libs/`.
5. Put any reusable cross-project utilities in the shared `utilities/` folder.
6. Put shared configuration (env vars, common settings) in the shared `config/` folder.

## Conventions

| Item | Convention |
|---|---|
| Project folder name | `snake_case` |
| Entry point | Always `main.py` (thin — no logic) |
| Application logic | Inside `libs/app_runner.py` and sibling modules |
| Config files | `.env`, `.yaml`, or `.json` inside `config/` |
| Data / collaterals | `.json`, `.csv`, `.xml` inside `data/` |
| Internal modules | Inside `libs/` with an `__init__.py` |
| Utilities | Standalone shared scripts in `utilities/`, not project-specific |

## Example — Multiple Projects Under One UserCode

```
jdoe/
├── config/                   # ← shared, created once
│   ├── settings.yaml
│   └── README.md
├── data/                     # ← shared, created once
│   ├── lookup_table.json
│   └── README.md
├── src/
│   ├── my_agent/             # ← project 1
│   │   ├── config/
│   │   │   ├── prompts.yaml
│   │   │   └── README.md
│   │   ├── data/
│   │   │   ├── input_payload.json
│   │   │   └── README.md
│   │   ├── libs/
│   │   │   ├── __init__.py
│   │   │   ├── app_runner.py
│   │   │   └── README.md
│   │   ├── main.py
│   │   └── README.md
│   └── my_console_app/       # ← project 2 (only this folder is new)
│       ├── config/
│       │   └── README.md
│       ├── data/
│       │   └── README.md
│       ├── libs/
│       │   ├── __init__.py
│       │   ├── app_runner.py
│       │   └── README.md
│       ├── main.py
│       └── README.md
├── utilities/                # ← shared, created once
│   ├── setup_env.py
│   └── README.md
└── README.md
```
