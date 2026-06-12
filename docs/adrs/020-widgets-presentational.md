---
status: accepted
date: 2026-06-09
deciders: edouard
---

# ADR-020: Widgets Are Presentational, App Owns Domain Logic

## Context and Problem Statement

The FileTreeTable widget was tracking `_last_highlighted_path` internally to decide whether to post `NodeHighlighted` messages. This mixed domain concerns (which file is "selected") with widget rendering concerns, creating fragile dedup logic that interacted badly with async message delivery.

## Decision Outcome

Widgets are **purely presentational**. They render what they're told and report all UI events. The **app** (controller) owns domain state and decides how to respond.

### Responsibility Split

| Layer                     | Responsibility                                                             |
| ------------------------- | -------------------------------------------------------------------------- |
| `FileTreeTable`           | Render rows, report cursor movements (always), handle expand/collapse      |
| `PreviewPane`             | Render content, guard against same-file re-renders (`_last_rendered_path`) |
| `GamrApp`                 | Decide whether a highlight event should trigger a preview update           |
| `models.py` / `services/` | Pure data, no UI awareness                                                 |

### What Changed

- `FileTreeTable.on_data_table_row_highlighted` always posts `NodeHighlighted` (no internal filtering)
- `restore_cursor(path)` simply moves the cursor (no `emit_highlight` parameter)
- `suppress_next_highlight()` removed
- `_last_highlighted_path` removed from the widget entirely
- `PreviewPane._last_rendered_path` is the single dedup guard (renders are expensive, movements are cheap)

### Consequences

- Good, because the widget has no domain knowledge — it's reusable and testable in isolation
- Good, because there's exactly one place to debug "why did/didn't the preview update?" (the app handler)
- Good, because async message delivery can't break dedup logic (it's not in the widget anymore)
- Neutral, the app receives more `NodeHighlighted` messages than before, but they're cheap to handle (path comparison)
