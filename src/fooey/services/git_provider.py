"""Git provider abstraction and Dulwich implementation."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from dulwich import porcelain
from dulwich.objects import Blob
from dulwich.repo import Repo


class GitStatus(Enum):
    UNTRACKED = "?"
    MODIFIED = "M"
    ADDED = "A"
    DELETED = "D"
    STAGED_MODIFIED = "SM"
    STAGED_ADDED = "SA"
    STAGED_DELETED = "SD"


@dataclass(frozen=True, slots=True)
class FileStats:
    lines_added: int
    lines_removed: int


@dataclass(frozen=True, slots=True)
class BlameInfo:
    last_author: str
    last_modified: int  # unix timestamp


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


class DulwichGitProvider(GitProvider):
    """Dulwich-based pure-Python git provider."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._repo: Repo | None = None
        try:
            self._repo = Repo(str(self.root))
        except Exception:
            pass

    def is_git_repo(self) -> bool:
        return self._repo is not None

    def get_status(self) -> dict[Path, GitStatus]:
        if not self._repo:
            return {}

        result: dict[Path, GitStatus] = {}
        status = porcelain.status(self._repo)

        # Staged changes: status.staged is a dict with keys 'add', 'modify', 'delete'
        for path_bytes in status.staged.get("add", []):
            result[self.root / os.fsdecode(path_bytes)] = GitStatus.STAGED_ADDED
        for path_bytes in status.staged.get("modify", []):
            result[self.root / os.fsdecode(path_bytes)] = GitStatus.STAGED_MODIFIED
        for path_bytes in status.staged.get("delete", []):
            result[self.root / os.fsdecode(path_bytes)] = GitStatus.STAGED_DELETED

        # Unstaged (working tree) changes: list of path bytes
        for path_bytes in status.unstaged:
            p = self.root / os.fsdecode(path_bytes)
            if p not in result:
                result[p] = GitStatus.MODIFIED

        # Untracked: list of str
        for path_str in status.untracked:
            result[self.root / path_str] = GitStatus.UNTRACKED

        return result

    def get_diff(self, path: Path) -> str:
        """Return unified diff for a file against HEAD."""
        if not self._repo:
            return ""

        rel = os.fsencode(str(path.relative_to(self.root)))
        try:
            head = self._repo[self._repo.head()]
            tree = self._repo[head.tree]
        except Exception:
            return ""

        # Get blob from HEAD
        old_blob = self._lookup_blob(tree, rel)
        # Get current working copy content
        try:
            new_content = path.read_bytes().splitlines(True)
        except OSError:
            new_content = []

        old_content = old_blob.splitlines(True) if old_blob else []

        import difflib

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
        added = sum(1 for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in diff.splitlines() if l.startswith("-") and not l.startswith("---"))
        return FileStats(lines_added=added, lines_removed=removed)

    def get_blame_info(self, path: Path) -> BlameInfo | None:
        """Get last author and timestamp for a file from git log."""
        if not self._repo:
            return None

        rel = str(path.relative_to(self.root))
        try:
            # Walk commits to find last one that touched this file
            for entry in self._repo.get_walker(paths=[rel.encode()], max_entries=1):
                commit = entry.commit
                author = commit.author.decode(errors="replace")
                # Strip email if present
                if "<" in author:
                    author = author.split("<")[0].strip()
                return BlameInfo(last_author=author, last_modified=commit.author_time)
        except Exception:
            pass
        return None

    def _lookup_blob(self, tree_obj: object, path_bytes: bytes) -> bytes | None:
        """Look up file content in a tree by path."""
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


class NullGitProvider(GitProvider):
    """No-op provider for non-git directories."""

    def is_git_repo(self) -> bool:
        return False

    def get_status(self) -> dict[Path, GitStatus]:
        return {}

    def get_diff(self, path: Path) -> str:
        return ""

    def get_file_stats(self, path: Path) -> FileStats | None:
        return None

    def get_blame_info(self, path: Path) -> BlameInfo | None:
        return None
