---
status: accepted
date: 2026-06-08
deciders: edouard
---

# ADR-016: Desktop-Style Folder Navigation with Arrow Keys

## Context and Problem Statement

How should arrow keys interact with the tree hierarchy? DataTable's default left/right moves between columns, which isn't useful for a tree-table where the first column is the primary focus.

## Decision Outcome

Override left/right arrow keys in tree mode to provide desktop-style folder navigation:

- **→** on collapsed directory: expand it
- **←** on expanded directory: collapse it
- **←** on file or collapsed dir: collapse the *parent* folder, cursor moves to parent
- **←** at root level: no action
- **←/→** in flat view modes: no action (no hierarchy)
- **Space**: toggle expand/collapse

### Consequences

- Good, because it matches macOS Finder, VS Code, and other tree UIs
- Good, because ← always "goes up" conceptually (collapse or navigate to parent)
- Neutral, overrides DataTable's default column navigation (acceptable since we use row cursor)

### File Watcher Interaction

When the file watcher detects changes, parent folders of changed files are automatically expanded to ensure changed files are visible.
