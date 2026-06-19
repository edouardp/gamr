---
status: accepted
date: 2026-06-20
deciders: edouard
---

# ADR-030: Git Worktree Support

## Context and Problem Statement

Git worktrees use a different layout: `.git` is a file (not a directory) containing a `gitdir:` pointer. The previous `repo_root` detection used `Path(self._repo.path)` which points to the gitdir (e.g., `.git/worktrees/feature/`), not the working directory. This broke all `relative_to(self.repo_root)` calls.

## Decision Outcome

**Walk up from the target directory to find `.git` (file or directory).** This works for both standard repos and linked worktrees because git guarantees a `.git` entry at the working tree root.

Additionally:
- Expose `git_common_dir` property (resolved path to the shared object store)
- Watch both per-worktree gitdir (HEAD, index) and commondir (packed-refs, refs/) for state changes
- Common dir watcher uses `recursive=True` to catch `refs/heads/*` updates

### File changes

| File              | Change                                                            |
| ----------------- | ----------------------------------------------------------------- |
| `git_provider.py` | `_find_worktree_root()` static method; `git_common_dir` property  |
| `file_scanner.py` | `start_watching()` accepts `git_common_root`, watches recursively |
| `app.py`          | Passes `git_common_dir` to scanner                                |

### Consequences

- Good, because gamr works correctly when started inside a linked worktree
- Good, because shared ref changes (branch switches in another worktree) are detected
- Neutral, multi-worktree parent folder browsing deferred to future work
