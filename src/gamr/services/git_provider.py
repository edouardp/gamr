"""Git provider abstraction and Dulwich implementation."""

from __future__ import annotations

import difflib
import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol

from dulwich import porcelain
from dulwich.ignore import IgnoreFilterManager
from dulwich.objects import Blob
from dulwich.repo import Repo

from gamr.models import BlameInfo, FileStats, GitStatus

logger = logging.getLogger(__name__)


class IgnoreFilter(Protocol):
    """Structural type shared with FileScanner's ignore filter support."""

    def is_ignored(self, path: str) -> bool | None: ...


class GitProvider(ABC):
    """Abstract interface for git operations. Swap implementations freely."""

    @abstractmethod
    def is_git_repo(self) -> bool: ...

    @abstractmethod
    def get_status(self) -> dict[Path, GitStatus]: ...

    @abstractmethod
    def get_diff(self, path: Path) -> str: ...

    @abstractmethod
    def get_file_stats(self, path: Path) -> FileStats | None: ...

    @abstractmethod
    def get_blame_info(self, path: Path) -> BlameInfo | None: ...

    def get_ignore_filter(self) -> IgnoreFilter | None:
        """Return gitignore filter if available."""
        return None


class DulwichGitProvider(GitProvider):
    """Dulwich-based pure-Python git provider."""

    def __init__(self, root: Path) -> None:
        self.target_path = root.resolve()
        self.repo_root = self.target_path
        self._repo: Repo | None = None
        try:
            self._repo = Repo.discover(str(self.target_path))
            self.repo_root = Path(self._repo.path).resolve()
        except Exception:
            pass

    def is_git_repo(self) -> bool:
        return self._repo is not None

    @property
    def git_dir(self) -> Path | None:
        """Return the .git directory path, or None if not a git repo."""
        if self._repo:
            return Path(self._repo.controldir())
        return None

    def get_ignore_filter(self) -> IgnoreFilter | None:
        if self._repo:
            manager = IgnoreFilterManager.from_repo(self._repo)
            prefix = self.target_path.relative_to(self.repo_root).as_posix()
            if prefix != ".":
                return _PrefixedIgnoreFilter(manager, prefix)
            return manager
        return None

    def get_status(self) -> dict[Path, GitStatus]:
        if not self._repo:
            return {}

        result: dict[Path, GitStatus] = {}
        try:
            status = porcelain.status(self._repo, untracked_files="all")
        except Exception:
            logger.exception("Failed to get git status")
            return {}

        # Staged changes take priority — process them first
        for path_bytes in status.staged.get("add", []):
            result[self.repo_root / os.fsdecode(path_bytes)] = GitStatus.STAGED_ADDED
        for path_bytes in status.staged.get("modify", []):
            result[self.repo_root / os.fsdecode(path_bytes)] = GitStatus.STAGED_MODIFIED
        for path_bytes in status.staged.get("delete", []):
            result[self.repo_root / os.fsdecode(path_bytes)] = GitStatus.STAGED_DELETED

        # Only mark unstaged if not already in staged (staged wins in priority)
        for path_bytes in status.unstaged:
            p = self.repo_root / os.fsdecode(path_bytes)
            if p not in result:
                result[p] = GitStatus.MODIFIED if os.path.lexists(p) else GitStatus.DELETED

        for path_str in status.untracked:
            decoded = os.fsdecode(path_str) if isinstance(path_str, bytes) else path_str
            result[self.repo_root / decoded] = GitStatus.UNTRACKED

        return result

    def get_diff(self, path: Path) -> str:
        """Return unified diff for a file against HEAD."""
        if not self._repo:
            return ""

        rel = os.fsencode(str(path.relative_to(self.repo_root)))
        try:
            # Resolve HEAD commit's tree to get the old version of the file
            head = self._repo[self._repo.head()]
            tree = self._repo[head.tree]
        except Exception:
            return ""

        old_blob = self._lookup_blob(tree, rel)
        try:
            new_content = path.read_bytes().splitlines(True)
        except OSError:
            new_content = []

        old_content = old_blob.splitlines(True) if old_blob else []

        diff_lines = difflib.unified_diff(
            [line.decode(errors="replace") for line in old_content],
            [line.decode(errors="replace") for line in new_content],
            fromfile=f"a/{path.name}",
            tofile=f"b/{path.name}",
        )
        return "".join(diff_lines)

    def get_file_stats(self, path: Path) -> FileStats | None:
        """Compute lines added/removed for a file vs HEAD."""
        diff = self.get_diff(path)
        if not diff:
            return None
        # Count diff lines starting with +/- but skip the +++ / --- header markers
        added = sum(1 for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++"))
        removed = sum(1 for ln in diff.splitlines() if ln.startswith("-") and not ln.startswith("---"))
        return FileStats(lines_added=added, lines_removed=removed)

    def get_blame_info(self, path: Path) -> BlameInfo | None:
        """Get last author and timestamp for a file from git log."""
        if not self._repo:
            return None

        rel = str(path.relative_to(self.repo_root))
        try:
            # Walk commits touching this file; max_entries=1 gets the most recent
            for entry in self._repo.get_walker(paths=[rel.encode()], max_entries=1):
                commit = entry.commit
                author = commit.author.decode(errors="replace")
                # Strip email portion from "Name <email>" format
                if "<" in author:
                    author = author.split("<")[0].strip()
                return BlameInfo(last_author=author, last_modified=commit.author_time)
        except Exception:
            logger.debug("Failed to get blame for %s", rel)
        return None

    def get_bulk_blame(self, paths: list[Path]) -> dict[Path, BlameInfo]:
        """Get blame info for many files in one log walk (much faster than per-file).

        Walks the commit history once, diffing each commit's tree against its parent
        to find which files changed. Stops when all requested files have been attributed.
        """
        if not self._repo:
            return {}

        from dulwich.diff_tree import tree_changes

        # Build set of relative paths we need blame for
        pending: dict[bytes, Path] = {}
        for p in paths:
            try:
                rel = p.relative_to(self.repo_root).as_posix().encode()
                pending[rel] = p
            except ValueError:
                continue

        if not pending:
            return {}

        result: dict[Path, BlameInfo] = {}
        try:
            for entry in self._repo.get_walker():
                if not pending:
                    break
                commit = entry.commit
                parent_tree_id = None
                if commit.parents:
                    try:
                        parent_tree_id = self._repo[commit.parents[0]].tree
                    except (KeyError, IndexError):
                        pass

                # Diff trees to get all changed paths in this commit
                changes = tree_changes(self._repo.object_store, parent_tree_id, commit.tree)
                for change in changes:
                    path_bytes = change.new.path if change.new else (change.old.path if change.old else None)
                    if path_bytes and path_bytes in pending:
                        abs_path = pending.pop(path_bytes)
                        author = commit.author.decode(errors="replace")
                        if "<" in author:
                            author = author.split("<")[0].strip()
                        result[abs_path] = BlameInfo(last_author=author, last_modified=commit.author_time)
        except Exception:
            logger.debug("Failed bulk blame walk")

        return result

    def _lookup_blob(self, tree_obj: object, path_bytes: bytes) -> bytes | None:
        """Look up file content in a tree by path."""
        # Walk each path component, descending through nested tree objects
        parts = path_bytes.split(b"/")
        current = tree_obj
        for part in parts:
            try:
                mode, sha = current[part]
                current = self._repo[sha]
            except (KeyError, TypeError):
                return None
        if isinstance(current, Blob):
            return current.data
        return None


class _PrefixedIgnoreFilter:
    """Translate paths relative to a browsed subdirectory into repo-relative paths."""

    def __init__(self, manager: IgnoreFilterManager, prefix: str) -> None:
        self._manager = manager
        self._prefix = prefix

    def is_ignored(self, path: str) -> bool | None:
        return self._manager.is_ignored(f"{self._prefix}/{path}")


class NullGitProvider(GitProvider):
    """No-op provider for non-git directories."""

    def is_git_repo(self) -> bool:
        return False

    @property
    def git_dir(self) -> Path | None:
        return None

    def get_status(self) -> dict[Path, GitStatus]:
        return {}

    def get_diff(self, path: Path) -> str:
        return ""

    def get_file_stats(self, path: Path) -> FileStats | None:
        return None

    def get_blame_info(self, path: Path) -> BlameInfo | None:
        return None
