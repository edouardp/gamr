---
status: accepted
date: 2026-06-08
deciders: edouard
---

# ADR-004: DataTable with Tree Semantics (Not Tree Widget)

## Context and Problem Statement

How do we display a file tree alongside metadata columns with proper alignment?

## Considered Options

1. Textual's Tree widget with render_label() override — single text column, manual padding
2. DataTable with tree-rendered first column — real columns, proper alignment
3. Side-by-side Tree + DataTable with scroll sync — complex sync logic

## Decision Outcome

Chosen option: **DataTable with tree semantics in column 1** because it gives us real, properly-aligned columns with headers (clickable for sorting), while the first column renders indentation and expand/collapse icons to simulate tree behavior.

### Consequences

- Good, because columns are independently sized, have headers, support sorting
- Good, because DataTable cursor_type="row" gives us keyboard navigation for free
- Bad, because we reimplement expand/collapse logic (space key handler)
- Neutral, tree state is internal; the DataTable is rebuilt on expand/collapse

## Supersedes

Initial implementation used Tree widget with render_label() appending padded metadata — but columns didn't align when filenames varied in length.
