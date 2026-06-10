---
status: accepted
date: 2026-06-09
deciders: edouard
---

# ADR-018: Diff Overview Bar

## Context and Problem Statement

When viewing long files with scattered changes, it's hard to see the overall change distribution without scrolling through the entire file. How do we provide a file-level change summary at a glance?

## Decision Outcome

Add a 1-column-wide overview bar docked to the right of the preview pane in full diff mode. It shows the entire file's change distribution vertically, color-coded:

- **Green** — added lines
- **Red** — removed lines
- **Yellow** — mixed (both added and removed in the same region)
- **Dim** — unchanged

### Two rendering styles (toggled via command palette):

1. **Line mode** (default) — `┃` (thick) for changed regions, `│` (thin dim) for unchanged
2. **Braille mode** — Unicode braille characters (U+2800 base) with dots lit where changes occur, packing 4 source lines per terminal row

### Visibility

- Shown only in full diff mode
- Hidden in unified diff and plain file preview modes
- Uses `display = False` when hidden (takes zero space)

### Consequences

- Good, because change hotspots are visible without scrolling
- Good, because it's only 1 character wide — minimal screen real estate
- Neutral, braille rendering depends on terminal font support
