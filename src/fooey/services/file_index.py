"""FileIndex service — merges file scanning with git metadata."""

from __future__ import annotations

from pathlib import Path

from fooey.models import FileEntry
from fooey.services.file_scanner import FileScanner
from fooey.services.git_provider import GitProvider


class FileIndex:
    """Builds and maintains a list of FileEntry objects from scanner + git."""

    def __init__(self, scanner: FileScanner, git: GitProvider) -> None:
        self.scanner = scanner
        self.git = git
        self.entries: dict[Path, FileEntry] = {}

    def build(self) -> list[FileEntry]:
        """Full rebuild of the file index."""
        files = self.scanner.scan()
        git_status = self.git.get_status()

        self.entries.clear()
        for path in files:
            try:
                stat = path.stat()
                size = stat.st_size
                mtime = stat.st_mtime
            except OSError:
                size = 0
                mtime = 0.0

            status = git_status.get(path)
            lines_added = None
            lines_removed = None
            if status and self.git.is_git_repo():
                file_stats = self.git.get_file_stats(path)
                if file_stats:
                    lines_added = file_stats.lines_added
                    lines_removed = file_stats.lines_removed

            entry = FileEntry(
                path=path,
                size=size,
                mtime=mtime,
                git_status=status,
                lines_added=lines_added,
                lines_removed=lines_removed,
            )
            self.entries[path] = entry

        return list(self.entries.values())

    def update_blame(self, path: Path) -> FileEntry | None:
        """Populate blame info for a single file. Called from background worker."""
        entry = self.entries.get(path)
        if not entry:
            return None
        info = self.git.get_blame_info(path)
        if info:
            entry.last_author = info.last_author
            entry.last_git_modified = info.last_modified
        return entry
