# libs — Internal Modules

This folder holds the application logic for this project. `main.py` is a thin entry point that delegates all work to modules here.

## Structure

| File | Responsibility |
|---|---|
| `app_runner.py` | Orchestrates the lifecycle: `setup()` → `start()` → `shutdown()` |
| `__init__.py` | Package marker |
| *(your modules)* | Add one module per logical concern (e.g., `parser.py`, `client.py`) |

## Guidelines

- `app_runner.py` is the **only module** imported directly by `main.py`.
- Break logic into focused modules and import them inside `AppRunner`.
- Avoid importing from outside `src/<project_name>/` — use `utilities/` for shared code.
