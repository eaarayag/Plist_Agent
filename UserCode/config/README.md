# config — Shared Configuration

This folder holds configuration files shared across **all projects** under this `UserCode`.

## Contents

| File | Purpose |
|---|---|
| `.env` | Environment variables (API keys, endpoints, flags) |
| `settings.yaml` | Common application settings |
| `*.json` | Shared JSON schemas or constants |

## Guidelines

- Do **not** commit secrets or credentials. Use `.env` and add it to `.gitignore`.
- Project-specific config overrides go in `src/<project_name>/config/`, not here.
