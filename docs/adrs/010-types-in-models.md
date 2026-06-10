---
status: accepted
date: 2026-06-08
deciders: edouard
---

# ADR-010: Types in Models, Not Services

## Context and Problem Statement

`GitStatus`, `FileStats`, and `BlameInfo` were originally defined in `git_provider.py`. This created a coupling where `models.py` imported from services — a potential circular dependency.

## Decision Outcome

Move all shared data types (`GitStatus`, `FileStats`, `BlameInfo`, `FileEntry`) to `models.py`. Services import from models, never the reverse.

### Dependency Direction

```
app.py → services/ → models.py
app.py → widgets/  → models.py
```

### Consequences

- Good, because no circular import risk
- Good, because models.py is the single source of truth for data shapes
- Good, because swapping git_provider implementations doesn't affect types
