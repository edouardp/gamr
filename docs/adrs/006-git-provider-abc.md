---
status: accepted
date: 2026-06-08
deciders: edouard
---

# ADR-006: GitProvider ABC for Swappable Implementations

## Context and Problem Statement

How do we keep the git integration decoupled so the implementation can be swapped without changing the rest of the codebase?

## Decision Outcome

Define a `GitProvider` ABC with methods: `is_git_repo()`, `get_status()`, `get_diff()`, `get_file_stats()`, `get_blame_info()`, `get_ignore_filter()`. Provide two implementations:

- `DulwichGitProvider` — full implementation using Dulwich
- `NullGitProvider` — no-op for non-git directories (graceful degradation)

### Consequences

- Good, because switching to pygit2 or git CLI requires only a new class
- Good, because NullGitProvider makes non-git mode trivial (no conditionals scattered through app)
- Good, because the app queries `git.is_git_repo()` once and hides git UI accordingly
