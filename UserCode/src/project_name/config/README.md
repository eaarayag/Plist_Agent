# config — Project Configuration

This folder holds configuration files specific to this project.

## Intended Content

| File | Purpose |
|---|---|
| `prompts.yaml` | Prompt templates (for agent projects) |
| `schema.json` | Input/output validation schemas |
| `settings.yaml` | Project-level settings and overrides |

## Guidelines

- Settings here override or extend the shared `config/` at the `UserCode` level.
- Do **not** commit secrets. Use environment variables or a `.env` file (gitignored).
