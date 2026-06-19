# Git Worktree Support

## Problem

Git worktrees have a different layout than a standard clone:

- **Standard repo:** `.git/` is a directory at the repo root containing objects, refs, HEAD, index.
- **Linked worktree:** `.git` is a *file* containing `gitdir: /path/to/main/.git/worktrees/<name>`. The actual control directory lives inside the main repo's `.git/worktrees/` folder, and objects/refs are shared via a `commondir`.

Currently `DulwichGitProvider.__init__()` sets `repo_root = Path(self._repo.path).resolve()`. In a worktree, `Repo.path` points to the gitdir (e.g., `/project/.git/worktrees/feature/`), not the working directory. This breaks all `path.relative_to(self.repo_root)` calls throughout the provider.

## Changes Required

### 1. Fix working tree root detection (`git_provider.py`)

Replace the naive `repo_root` assignment with an upward walk to find the `.git` entry:

```python
def __init__(self, root: Path) -> None:
    self.target_path = root.resolve()
    self.repo_root = self.target_path
    self._repo: Repo | None = None
    try:
        self._repo = Repo.discover(str(self.target_path))
        self.repo_root = self._find_worktree_root(self.target_path)
    except Exception:
        pass

@staticmethod
def _find_worktree_root(start: Path) -> Path:
    """Walk up to find the directory containing .git (file or directory)."""
    current = start
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return start
```

This works for both layouts:
- Standard: finds the `.git/` directory → returns its parent.
- Worktree: finds the `.git` file → returns its parent (the worktree checkout root).

### 2. Expose `git_common_dir` (`git_provider.py`)

Add a property for the shared object/ref store. `Repo.commondir()` returns the
repo's own controldir when no `commondir` file exists, so this is safe for both
standard repos and linked worktrees:

```python
@property
def git_common_dir(self) -> Path | None:
    """Shared git directory (same as git_dir for non-worktrees)."""
    if self._repo:
        try:
            return Path(self._repo.commondir())
        except Exception:
            return self.git_dir
    return None
```

### 3. Watch both gitdirs (`file_scanner.py`)

In a worktree, ref changes (branches, tags) happen in the shared `commondir`, not the per-worktree control dir. The scanner needs to watch both:

- **Per-worktree dir** (non-recursive): `HEAD`, `index` changes
- **Common dir** (recursive): `packed-refs`, `refs/heads/*`, `refs/tags/*` changes

```python
def start_watching(self, git_root: Path | None = None, git_common_root: Path | None = None) -> None:
    # ... existing observer setup ...
    if git_root and git_root.exists():
        git_handler = _GitHandler(self.queue)
        self._observer.schedule(git_handler, str(git_root), recursive=False)
    if git_common_root and git_common_root != git_root and git_common_root.exists():
        git_handler = _GitHandler(self.queue)
        self._observer.schedule(git_handler, str(git_common_root), recursive=True)
```

### 4. Wire it up (`app.py`)

Pass both directories when starting the watcher:

```python
self._scanner.start_watching(
    git_root=self._git.git_dir,
    git_common_root=self._git.git_common_dir,
)
```

## What Already Works

- `Repo.discover()` — Dulwich follows the `.git` file's `gitdir:` pointer correctly.
- `porcelain.status()` — operates on the discovered repo object, handles worktrees internally.
- `get_walker()` (blame) — same, works against the shared object store.
- `IgnoreFilterManager.from_repo()` — loads `.gitignore` from the working tree.
- `controldir()` (used by `git_dir` property) — already returns the per-worktree gitdir.

## Risk Areas to Test

| Area                      | Concern                                                                                                                                   |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Path relativization       | All `path.relative_to(self.repo_root)` must use the worktree root, not the gitdir                                                         |
| `_GitHandler` state files | `HEAD` and `index` are per-worktree (in `controldir`); `packed-refs` is shared (in `commondir`)                                           |
| `info/exclude`            | Exists in both per-worktree and shared dirs; verify which takes precedence                                                                |
| Default ignores           | The `.git` ignore pattern in `FileScanner` must not hide the `.git` _file_ before the provider reads it (it won't — provider inits first) |

## Scope

This is a focused change — 4 files touched, no new dependencies. The `NullGitProvider` and all non-git paths are unaffected.

## Test Plan

Integration test using a real worktree fixture (`tests/test_worktree.py`):

1. **Fixture:** Create a temp git repo, add a commit, then `git worktree add` a linked worktree.
2. **Root detection:** Verify `DulwichGitProvider(worktree_path).repo_root` equals the worktree checkout dir.
3. **`git_common_dir`:** Verify it points to the main repo's `.git/` (not the per-worktree dir).
4. **Status:** Modify a file in the worktree, verify `get_status()` reports it correctly.
5. **Diff/blame:** Verify `get_diff()` and `get_blame_info()` work from the worktree path.
6. **Path relativization:** Verify no `ValueError` from `relative_to()` on worktree files.
