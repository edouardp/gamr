---
status: accepted
date: 2026-06-08
deciders: edouard
---

# ADR-013: Spaced Paths for Readability

## Context and Problem Statement

In flat path view, paths like `src/services/git_provider.py` can be hard to scan quickly. How do we improve readability?

## Decision Outcome

Add spaces around path separators by default: `src / services / git_provider.py`. This is toggled via the command palette.

### Consequences

- Good, because path components are visually distinct
- Good, because the separator still reads naturally as a path
- Neutral, takes slightly more horizontal space
