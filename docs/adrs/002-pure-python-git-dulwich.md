---
status: accepted
date: 2026-06-08
deciders: edouard
---

# ADR-002: Pure Python Git via Dulwich

## Context and Problem Statement

How should we interact with git repositories? We need status, diff, blame, and gitignore support without requiring the git binary.

## Considered Options

1. Dulwich — pure Python, no compiled deps, no git binary needed
2. pygit2 — libgit2 bindings, fast but requires native compilation
3. GitPython — wraps the git CLI, requires git installed
4. Shell out to git — simple but fragile, requires git binary

## Decision Outcome

Chosen option: **Dulwich** because it's pure Python (works anywhere Python does), has no compiled dependencies, provides porcelain + low-level APIs for status/diff/log, and includes `IgnoreFilterManager` for proper .gitignore handling.

### Consequences

- Good, because zero native deps — easy install on any platform
- Good, because `IgnoreFilterManager` handles nested .gitignore, negation, and global excludes
- Bad, because some operations (blame) are slower than native git
- Mitigation: expensive operations run in background thread workers

## Design Note

The `GitProvider` ABC allows swapping Dulwich for another backend (e.g., pygit2 for performance) without changing the rest of the app.
