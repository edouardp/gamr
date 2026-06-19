---
status: accepted
date: 2026-06-20
deciders: edouard
---

# ADR-032: Preview Controller Extraction

## Context and Problem Statement

`app.py` exceeded 870 lines. The preview orchestration logic (which file to show, scroll positions, diff mode dispatch, follow-mode scrolling) was the largest self-contained section.

## Decision Outcome

**Extract a `PreviewController` class into `src/gamr/preview.py`.** It owns preview state and domain decisions; the widget remains presentational.

### Responsibilities

| Layer                  | Owns                                                                                            |
| ---------------------- | ----------------------------------------------------------------------------------------------- |
| `PreviewController`    | `previewed_path`, `scroll_positions`, `_known_hunks`, render dispatch, follow-mode scroll logic |
| `PreviewPane` (widget) | Syntax highlighting, diff rendering, scroll mechanics, overview bar                             |
| `GamrApp`              | Async preview worker (large files), keybinding dispatch, widget queries                         |

### Consequences

- Good, because `app.py` reduced by ~100 lines
- Good, because preview logic is testable without the full TUI
- Good, because the controller is a plain class (no Textual dependency except PreviewPane type)
