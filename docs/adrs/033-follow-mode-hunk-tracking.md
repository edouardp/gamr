---
status: accepted
date: 2026-06-20
deciders: edouard
---

# ADR-033: Follow Mode Hunk Tracking

## Context and Problem Statement

Follow mode previously scrolled to the first diff hunk on every file change. This was wrong in two ways: (1) it jumped to old hunks, not the new change, and (2) it scrolled even when the change was already visible, disorienting the user.

## Decision Outcome

**Track known hunk start lines per file; scroll only to genuinely new hunks, and only if off-screen.**

### Mechanism

1. When a file is first previewed (via navigation), `_snapshot_hunks()` records all current hunk start lines in `_known_hunks[path]`
2. On follow-mode update, extract current hunks and diff against the known set
3. New hunks = `current - known`; scroll target = `max(new_hunks)` (latest in file)
4. If target is already visible in the viewport → re-render in place, no scroll
5. If target is off-screen → scroll to it
6. Update `_known_hunks[path]` for next iteration

### Where state lives

- `_known_hunks` lives in `PreviewController` (domain layer), not the widget
- `is_source_line_visible()` is a viewport query on `PreviewPane` (widget utility)
- J/K hunk navigation is independent — operates on all hunks, unrelated to follow tracking

### Consequences

- Good, because the preview stays stable when edits happen within the visible area
- Good, because genuinely new changes (new hunk locations) are highlighted by scrolling to them
- Neutral, hunk start lines are an approximation (a modified hunk that shifts position appears as new+removed)
