---
status: accepted
date: 2026-06-08
deciders: edouard
---

# ADR-008: Three View Modes with Sort-Triggered Mode Switching

## Context and Problem Statement

Users need different ways to view files: hierarchical tree, flat filename list, and flat with relative paths. Sorting doesn't make sense in tree mode.

## Decision Outcome

Three view modes cycled with `v`:
- **TREE** — directories expandable, files nested
- **FLAT_NAME** — leaf filenames only, no hierarchy
- **FLAT_PATH** — relative paths (e.g., `src / worker / foo.py`)

### Sort Interaction

When a column header is clicked for sorting:
1. If in TREE mode, automatically switch to FLAT_PATH (sort needs a flat list)
2. Remember the pre-sort mode was TREE
3. When sort is removed (third click), restore TREE mode

### Consequences

- Good, because tree view preserves spatial understanding of project structure
- Good, because flat views enable meaningful column sorting
- Good, because automatic mode switching is transparent to the user
