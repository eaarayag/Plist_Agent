# utilities — Shared Utilities

This folder holds reusable scripts, classes, and data structures shared across **all projects** under this `UserCode`.

## Intended Content

| Type | Examples |
|---|---|
| Helper classes | Common data structures, base classes |
| Utility scripts | Setup scripts, data converters, file parsers |
| Shared modules | Logging wrappers, common validators |

## Guidelines

- Code here must be **project-agnostic** — no project-specific logic.
- Utilities are imported by projects as needed, not executed directly (unless they are standalone scripts).
- Keep each utility focused on a single responsibility.
