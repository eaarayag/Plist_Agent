# data — Project Collaterals

This folder holds data files used exclusively by this project.

## Intended Content

| Type | Examples |
|---|---|
| JSON | Input payloads, mock data, output samples |
| CSV | Project-specific datasets or test fixtures |
| XML / YAML | Templates or structured input files |

## Guidelines

- Only place files here if they are consumed by **this project only**.
- Files shared across projects belong in the top-level `data/` folder.
- Do not store large binary files. Use external storage and reference them by path/URL in config.
