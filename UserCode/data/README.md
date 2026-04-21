# data — Shared Collaterals

This folder holds data files shared across **all projects** under this `UserCode`.

## Intended Content

| Type | Examples |
|---|---|
| JSON | Lookup tables, shared schemas, reference data |
| CSV | Common datasets reused by multiple projects |
| XML / YAML | Shared templates or structured reference files |

## Guidelines

- Only place files here if **more than one project** needs them.
- Project-specific data files belong in `src/<project_name>/data/`.
- Do not store large binary files. Use external storage and reference them by path/URL in config.
