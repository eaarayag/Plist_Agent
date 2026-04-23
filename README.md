# Plist Agent — Collaborative Repository

This repository hosts **console applications and tools** developed collaboratively across the organization.

## Repository Structure

```
.
├── .github/
│   └── agents/   # Workspace custom Copilot agents (.agent.md)
├── docs/         # Repository-wide documentation and contribution guidelines
├── UserCode/     # Standard project skeleton (start here for new projects)
└── README.md
```

## Starting a New Project

Every application follows the standard skeleton defined in [UserCode/README.md](UserCode/README.md):

```
<UserCode>/
├── config/          # Shared across all projects — created once
├── data/            # Shared collaterals — created once
├── src/
│   └── <project_name>/   # ← only this is added per new project
│       ├── config/
│       ├── data/
│       ├── libs/
│       │   ├── app_runner.py
│       │   └── __init__.py
│       ├── main.py
│       └── README.md
├── utilities/       # Shared scripts and tools — created once
└── README.md
```

`config/`, `data/`, and `utilities/` hold shared classes, data structures, and settings reused across projects. **Only add a new `src/<project_name>/` folder** for each new project — copy it from [UserCode/src/project_name/](UserCode/src/project_name/).

## Contributing

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.
