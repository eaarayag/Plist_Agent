# libs

Internal modules for plist_extractor. All application logic lives here.

| Module | Responsibility |
|---|---|
| `app_runner.py` | `AppRunner` lifecycle: setup → start → shutdown |
| `Parser.py` | Tokenizes a `.plist` file into `PlistFile` / `PlistBlock` / `PlistEntry` dataclasses |
| `Matcher.py` | Matches `GlobalPList` names against filter criteria; handles full-content expansion and skip patterns |
| `Extractor.py` | Orchestrates extraction: finds content plists, PLBs, hotreset plists; trims multi-partition PLBs |
| `Generator.py` | Writes the output `.plist` file with `Version 5.0;` header and section separators |
