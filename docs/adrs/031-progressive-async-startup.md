---
status: accepted
date: 2026-06-20
deciders: edouard
---

# ADR-031: Progressive Async Startup

## Context and Problem Statement

On large repos, `on_mount` blocked while scanning files, computing git status, and counting lines. The UI was unresponsive until all data was ready.

## Decision Outcome

**Show the UI shell immediately, defer all I/O to a background worker.** The startup sequence is now:

1. `on_mount` (sync): compose widgets, restore persisted state, show `LoadingIndicator`
2. `_initial_load` (background thread): `build_fast()` — scan + git status, skip line counting
3. `_on_initial_load_complete` (main thread callback): remove loading indicator, show split pane, populate tree
4. Deferred workers: line counts, diff stats, blame fill in progressively

### Data pipeline

| Data                               | Phase                            | Blocks UI? |
| ---------------------------------- | -------------------------------- | ---------- |
| UI shell (header, toolbar, footer) | Sync mount                       | No         |
| File list + sizes + git status     | Background (`build_fast`)        | No         |
| Line counts (row_count)            | Background (`_load_line_counts`) | No         |
| Diff stats (+/- lines)             | Background (`_load_diff_stats`)  | No         |
| Blame (author, time)               | Background (`_load_blame_data`)  | No         |

### Consequences

- Good, because the TUI renders within one frame regardless of repo size
- Good, because the native `LoadingIndicator` fills the content area during load
- Neutral, columns show empty values briefly before workers complete
