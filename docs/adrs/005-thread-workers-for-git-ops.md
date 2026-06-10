---
status: accepted
date: 2026-06-08
deciders: edouard
---

# ADR-005: Thread Workers for Blocking Git Operations

## Context and Problem Statement

Textual runs on a single asyncio event loop. Dulwich operations (status, diff, blame) are synchronous and can block for seconds on large repos. How do we prevent UI freezes?

## Decision Outcome

Use Textual's `@work(thread=True)` decorator to run blocking operations in thread workers.

### Concurrency Architecture

| Operation | Worker Type | Strategy |
|-----------|------------|----------|
| Git status | Thread, exclusive | Debounced after file changes |
| Diff stats (+/- lines) | Thread, exclusive | Deferred after initial load |
| Git blame/log | Thread, group | Progressive per-file updates |
| File watcher | Thread, long-running | Polls queue every 0.5s |
| Fuzzy filter | Inline (sync) | Fast enough for <10k files |

### Key Constraints

- **watchdog → UI**: Events arrive on watchdog's thread; bridged via `call_from_thread()` or `post_message()` (thread-safe)
- **Dulwich → UI**: Results pushed via `call_from_thread()`; check `worker.is_cancelled` before updating
- **Exclusive workers**: Cancel previous work when user changes selection/filter (prevents stale writes)

### Consequences

- Good, because UI stays responsive during expensive git operations
- Good, because Textual manages worker lifecycle (auto-cleanup on widget removal)
- Neutral, blame columns show "..." placeholder while loading
