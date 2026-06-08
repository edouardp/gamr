"""Data models for Fooey."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from fooey.services.git_provider import BlameInfo, GitStatus


@dataclass
class FileEntry:
    """All displayable data for a single file."""

    path: Path
    size: int = 0
    mtime: float = 0.0
    git_status: GitStatus | None = None
    lines_added: int | None = None
    lines_removed: int | None = None
    # Expensive fields populated by background worker
    last_author: str | None = None
    last_git_modified: int | None = None  # unix timestamp

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def is_dir(self) -> bool:
        return self.path.is_dir()
