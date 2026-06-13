---
status: accepted
date: 2026-06-14
deciders: edouard
---

# ADR-029: Side-by-Side Diff Modal

## Context and Problem Statement

The existing diff modes (full, gutter, unified) show changes inline within a single file view. For reviewing complex changes, a side-by-side view showing the old file (HEAD) next to the new file (working copy) with aligned padding is more intuitive.

## Decision Outcome

**Add a modal popup (`s` key) that shows the full old and new files side by side in a single scrollable view.** The modal covers 95% of the screen and includes syntax highlighting, character-level inline diff highlighting, and a diff overview bar.

### Architecture

- `SideBySideDiffScreen` is a Textual `ModalScreen[int]` that returns the current source line on dismiss
- Both files are rendered into a **single `Text` object** with fixed-width columns separated by a `│` divider — this eliminates scroll sync issues entirely
- The `VerticalScroll` container receives focus on mount for native scroll handling (keyboard, mouse wheel, scrollbar drag) with zero latency
- `GitProvider.get_old_content()` retrieves the HEAD version of the file via Dulwich's blob lookup

### Alignment Algorithm

The unified diff is parsed to identify hunks. Within each hunk:
1. Removed and added lines are collected into buffers
2. Lines are paired 1:1 as "changed" (orange background on both sides)
3. Excess removed lines become "removed" (red background left, grey padding right)
4. Excess added lines become "added" (green background right, grey padding left)
5. Context lines pass through as "same" (no background)

This produces equal row counts on both sides with blank padding where needed.

### Sub-line Highlighting

For "changed" line pairs, `difflib.SequenceMatcher` finds character-level differences. The specific differing characters get a brighter background color, making it easy to spot e.g. `=` → `==`.

### Key Behaviors

- **`s`** toggles the modal (opens if closed, closes if open)
- **`q`/`escape`** dismiss the modal (don't quit the app)
- Scroll position syncs bidirectionally with the preview pane (opens at same position, restores on close)
- Live updates when the file changes on disk (preserves scroll position)
- Diff overview bar on the right shows change map (orange/green/red)
- App-level priority keybindings are guarded with `_has_modal()` to prevent interference

### Consequences

- Good, because single-Text rendering guarantees perfect row alignment without scroll sync logic
- Good, because native `VerticalScroll` focus gives responsive scrolling without manual event forwarding
- Good, because character-level diff highlighting makes small changes immediately visible
- Good, because live refresh keeps the view current during active development
- Neutral, long lines are truncated to half screen width (no horizontal scroll)
