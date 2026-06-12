---
status: accepted
date: 2026-06-12
deciders: edouard
---

# ADR-025: Vim-Style Keybindings and Preview Pane Focus

## Context and Problem Statement

The preview pane had no keyboard navigation — users could only scroll via mouse. There was also no way to jump between diff hunks without scrolling manually.

## Decision Outcome

Add vim-style keybindings that context-switch based on focused pane:

- `j`/`k` — cursor up/down in file tree; scroll up/down in preview
- `space` — expand/collapse in tree; page down in preview
- `J`/`n` and `K`/`N` — jump to next/prev diff hunk (preview only)
- Arrow keys, page up/down — scroll preview when focused

### Key design decisions

1. **PreviewPane is now focusable** (`can_focus = True`) so tab switching and key bindings work
2. **Hunk navigation groups contiguous changed lines** — a 20-line addition is one hunk, not 20 jump targets
3. **Hunk jumps show 3 lines of context** above the target line
4. **Scroll position saved around unified diff mode** — unified diff only contains changes, so its scroll position can't represent the user's original full-file position. The source line is saved before entering unified mode and restored when leaving.
5. **Drag-select highlight throttled** to 30ms to prevent lag on large files

### Consequences

- Good, because keyboard-only navigation is now possible in both panes
- Good, because hunk jumping makes reviewing large diffs much faster
- Neutral, `space` has different behaviour depending on focused pane (consistent with the existing tree expand/collapse vs preview scroll pattern)
