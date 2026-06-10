---
status: accepted
date: 2026-06-08
deciders: edouard
---

# ADR-001: Use Textual as TUI Framework

## Context and Problem Statement

Which Python TUI framework should we use to build an interactive, responsive file browser with split panes, data tables, and async workers?

## Considered Options

1. Textual — modern, CSS-like styling, async-native, rich widget library
2. urwid — mature but lower-level, manual layout
3. blessed/curses — very low-level, no built-in widgets

## Decision Outcome

Chosen option: **Textual** because it provides DataTable, Tree, reactive attributes, CSS styling, built-in Workers API for background tasks, and a pilot testing framework. Its async event loop integrates cleanly with our concurrency needs.

### Consequences

- Good, because DataTable gives us proper column alignment and headers
- Good, because Workers API handles thread↔UI bridging elegantly
- Good, because CSS separation keeps styling maintainable
- Neutral, because Textual is relatively new and API may evolve
