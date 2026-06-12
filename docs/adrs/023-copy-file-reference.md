---
status: accepted
date: 2026-06-10
deciders: edouard
---

# ADR-023: Copy File Reference from Preview Pane

## Context

When reviewing agent work, you need to quickly reference specific file lines in a coding assistant. Manually typing `path/to/file.py:42` is tedious.

## Decision

Double-click or drag-select lines in the preview pane to copy a file:line reference to the clipboard.

### Interactions

| Action            | Result                | Feedback                                            |
| ----------------- | --------------------- | --------------------------------------------------- |
| Double-click      | Copy `path:line`      | Flash highlight + notification                      |
| Drag across lines | Copy `path:start-end` | Live highlight during drag, notification on release |
| Single click      | Nothing               | —                                                   |

### Source Line Mapping

All three diff modes use `_row_to_source` to map display rows to actual file line numbers:
- **Gutter**: 1:1
- **Full diff**: removed lines map to next source line
- **Unified**: context/added lines valid, removed/headers return 0 (invalid → no-op)

### Highlight

Selection uses `#44475a` background (Dracula selection color, visible against Monokai `#272822`). Clears 0.5s after copy completes.
