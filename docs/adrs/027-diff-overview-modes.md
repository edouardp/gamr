---
status: accepted
date: 2026-06-12
deciders: edouard
---

# ADR-027: Diff Overview Modes and Scaling

## Context and Problem Statement

The diff overview bar needs to show change distribution at varying file sizes, from files that fit on screen to files with thousands of lines. Different Unicode character sets offer different vertical densities.

## Decision Outcome

Five overview modes cycled via `o` keybinding, all rendering on the right side of each cell for visual consistency:

| Mode     | Density | Characters                           |
| -------- | ------- | ------------------------------------ |
| Line     | 1×/row  | `▐` or space                         |
| Quadrant | 2×/row  | `▝` `▗` `▐`                          |
| Sextant  | 3×/row  | Right-column sextant (U+1FB00 block) |
| Braille  | 4×/row  | Right-column braille dots            |
| Off      | —       | Bar hidden                           |

### Scaling principles

1. **1:1 alignment when file fits**: When `total_lines ≤ overview_height`, each row maps to exactly one source line with a full-height mark. Changed lines visually align with their preview line.

2. **Sub-cell scaling when file overflows**: When `total_lines > overview_height`, source lines are distributed across `height × slots_per_row` sub-cell slots. Each slot covers a proportional range of source lines.

3. **Never miss a change**: If any changed line falls within a slot's range, that slot is lit. No sampling or aliasing.

4. **Unified rendering**: A single `_render_subcell` method handles all modes via a `char_fn` callback that maps slot states to characters.

### Visibility

- Shown in full diff and gutter modes (when changes exist)
- Hidden in unified diff, plain file preview, and when "off" is selected
- Style persisted between sessions

### Consequences

- Good, because users can choose density appropriate to their terminal and file size
- Good, because 1:1 mode gives immediate visual correlation with the preview
- Good, because the unified renderer eliminates code duplication
- Neutral, sextant mode requires Unicode 13.0 terminal support (Ghostty, Kitty, WezTerm)
