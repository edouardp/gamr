"""Data models for Gamr."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class GitStatus(Enum):
    UNTRACKED = "?"
    MODIFIED = "M"
    ADDED = "A"
    DELETED = "D"
    STAGED_MODIFIED = "SM"
    STAGED_ADDED = "SA"
    STAGED_DELETED = "SD"


class DiffMode(Enum):
    """Preview pane diff display modes."""

    FULL = "full"  # Full file with diff highlighting
    GUTTER = "gutter"  # File with gutter markers (plain if no changes)
    UNIFIED = "unified"  # Standard unified diff


@dataclass(frozen=True, slots=True)
class FileStats:
    lines_added: int
    lines_removed: int


@dataclass(frozen=True, slots=True)
class BlameInfo:
    last_author: str
    last_modified: int  # unix timestamp from git author_time


@dataclass
class FileEntry:
    """All displayable data for a single file.

    Mutable fields (lines_added, last_author, etc.) are populated lazily
    by background workers after initial build.
    """

    path: Path
    size: int = 0
    mtime: float = 0.0
    git_status: GitStatus | None = None
    lines_added: int | None = None
    lines_removed: int | None = None
    last_author: str | None = None
    last_git_modified: int | None = None  # unix timestamp
    row_count: int | None = None  # line count for text files, None for binary

    @property
    def name(self) -> str:
        return self.path.name
