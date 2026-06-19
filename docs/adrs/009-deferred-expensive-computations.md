---
status: accepted
date: 2026-06-08
deciders: edouard
---

# ADR-009: Deferred Expensive Computations

## Context and Problem Statement

Computing diff stats (+/- lines) and blame info for every file blocks startup. Large repos with many modified files would make the app feel sluggish on launch.

## Decision Outcome

**Defer all expensive per-file computations to background workers.** The initial `FileIndex.build()` only collects file metadata (stat) and git status (a single `porcelain.status()` call). Per-file operations run after the UI is visible:

| Data                   | When computed                                | Worker group  |
| ---------------------- | -------------------------------------------- | ------------- |
| File size, mtime       | `build_fast()` (instant via `stat()`)        | —             |
| Git status             | `build_fast()` (single `porcelain.status()`) | —             |
| Line count (row_count) | Background after mount                       | `line_counts` |
| Diff stats (+/- lines) | Background after mount                       | `diff_stats`  |
| Blame (author, time)   | Background on mount or column toggle         | `blame`       |

### Consequences

- Good, because the UI appears immediately with file names and statuses
- Good, because columns show "..." while data loads, then update progressively
- Neutral, data appears in two phases (but this is standard for IDEs/file managers)
