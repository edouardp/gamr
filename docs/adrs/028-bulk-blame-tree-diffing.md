---
status: accepted
date: 2026-06-12
deciders: edouard
---

# ADR-028: Bulk Blame via Single Log Walk with Tree Diffing

## Context and Problem Statement

The blame columns (last author, last modified) previously used per-file `get_walker(paths=[file], max_entries=1)` calls. On a repo with 833 files and 4500 commits, this took ~200s because each call independently walks the commit graph.

## Decision Outcome

**Walk the commit log once and diff each commit's tree against its parent using Dulwich's `tree_changes()`.** This produces all changed file paths per commit in a single tree comparison. We maintain a set of "pending" files and remove them as they're attributed, stopping early once all files are resolved.

### Algorithm

```
pending = {relative_path: absolute_path for each file needing blame}
for commit in log_walk:
    if pending is empty: break
    changes = tree_changes(parent_tree, commit_tree)
    for change in changes:
        if change.path in pending:
            attribute(pending.pop(change.path), commit.author, commit.time)
```

### Performance

| Approach        | Time (833 files, 4504 commits) |
| --------------- | ------------------------------ |
| Per-file walker | ~202s                          |
| Bulk tree diff  | ~1.7s                          |

### Caching

Blame results are cached in `FileIndex._blame_cache` and survive `build()` rebuilds. On git state change:
- If specific `changed_paths` are known: only those entries are evicted
- If no paths (e.g., branch switch): entire cache is cleared

The blame worker skips files that already have `last_author` set (from cache).

### Consequences

- Good, because blame loads in <2s even on large repos (120x faster)
- Good, because early termination means small repos with recent activity resolve almost instantly
- Good, because caching means subsequent file changes only re-blame affected files
- Neutral, requires walking all commits for files only present in the initial commit
