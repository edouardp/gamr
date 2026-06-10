---
status: accepted
date: 2026-06-08
deciders: edouard
---

# ADR-003: Watchdog with Polling Fallback for File Watching

## Context and Problem Statement

How do we detect filesystem changes in real-time to keep the file tree up to date?

## Considered Options

1. watchdog — cross-platform, uses FSEvents on macOS, inotify on Linux
2. OS-native only (PyObjC/fsevents) — macOS-specific
3. Pure polling — simple but high latency and CPU cost
4. watchdog + polling fallback — best of both

## Decision Outcome

Chosen option: **watchdog with polling fallback** because watchdog provides efficient native filesystem events on all platforms, and polling ensures the app still works if watchdog fails (e.g., network filesystems, Docker volumes).

### Consequences

- Good, because native events are near-instant on macOS (FSEvents)
- Good, because polling fallback ensures robustness on edge-case filesystems
- Neutral, watchdog runs its own thread — requires queue-based bridging to Textual's event loop
