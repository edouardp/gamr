---
status: accepted
date: 2026-06-10
deciders: edouard
---

# ADR-021: Gutter Diff Mode

## Context

Full diff mode inserts removed lines inline which changes the line count and can be visually noisy. Unified diff loses the syntax-highlighted source context. A lighter-weight indicator was wanted.

## Decision

Add a "gutter" diff mode that shows the full syntax-highlighted file with a single change column between line numbers and content:

- `●` (orange #ff8c00) — changed lines (added with corresponding removals before them)
- `+` (green) — purely added lines
- `_` (red) — marks lines where deletions follow (visually sits between lines)

The diff overview bar is shown in gutter mode (same as full diff).

## Cycle Order

full → gutter → unified (wraps). Gutter mode replaces the old plain file view — when a file has no changes, gutter renders identically to a plain file (no gutter column, no overview bar).
