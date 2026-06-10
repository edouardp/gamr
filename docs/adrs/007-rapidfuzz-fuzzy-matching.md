---
status: accepted
date: 2026-06-08
deciders: edouard
---

# ADR-007: RapidFuzz for Fuzzy Filename Matching

## Context and Problem Statement

We need fzf-like fuzzy filename filtering that works inline (synchronously) without blocking the UI.

## Considered Options

1. RapidFuzz — C extension with pure Python fallback, very fast
2. thefuzz — pure Python Levenshtein, slower
3. Custom substring/regex — simple but no fuzzy matching

## Decision Outcome

Chosen option: **RapidFuzz** because it provides `partial_ratio` scoring fast enough to run synchronously on every keystroke for typical repos (<10k files), and has a pure Python fallback ensuring it works on all platforms without compilation.

### Consequences

- Good, because inline filtering avoids async complexity
- Good, because partial_ratio handles substring matches intuitively
- Neutral, scoring threshold (50) may need tuning for large repos
