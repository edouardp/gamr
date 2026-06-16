---
status: accepted
date: 2026-06-08
deciders: edouard
---

# ADR-017: Three Diff Display Modes

## Context and Problem Statement

Users need different levels of diff detail. A unified diff loses file context. A plain preview loses change visibility.

## Decision Outcome

Three modes cycled with `d` (forward) and `D` (reverse):

1. **Full diff** (default) — Complete file with syntax highlighting + diff markers (`+`/`-`) and colored backgrounds on changed lines. Removed lines shown inline.
2. **Gutter diff** — Full file with syntax highlighting and a single gutter column showing change markers (`●` modified, `+` added, `_` deleted). No inline removed lines.
3. **Unified diff** — Standard coloured unified diff output (no syntax highlighting).

See also ADR-021 which introduced the gutter mode, replacing the original "file preview" mode.

### Rendering

Full diff and gutter mode share the same renderer (`_render_highlighted`). The difference is whether full diff markers/backgrounds or a single gutter column is shown. This ensures consistent appearance (same line numbers, syntax theme, spacing) when toggling.

### Scroll Preservation

When switching modes, the source line at the top of the viewport is remembered and restored via a display-row-to-source-line mapping. This accounts for the full diff mode having extra rows (removed lines).

### Consequences

- Good, because full diff is the most useful default (see changes in context)
- Good, because shared rendering eliminates visual jarring when switching
- Neutral, full diff is slightly more expensive to render (diff parsing + highlighting)
