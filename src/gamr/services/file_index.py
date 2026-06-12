"""FileIndex service — merges file scanning with git metadata."""

from __future__ import annotations

from pathlib import Path

from gamr.models import BlameInfo, FileEntry, GitStatus
from gamr.services.file_scanner import FileScanner
from gamr.services.git_provider import GitProvider


class FileIndex:
    """Builds and maintains a list of FileEntry objects from scanner + git."""

    def __init__(self, scanner: FileScanner, git: GitProvider) -> None:
        self.scanner = scanner
        self.git = git
        self.entries: dict[Path, FileEntry] = {}
        self._blame_cache: dict[Path, BlameInfo] = {}

    def build(self) -> list[FileEntry]:
        """Full rebuild of the file index (without diff stats — those are deferred)."""
        files = self.scanner.scan()
        git_status = self.git.get_status()

        self.entries.clear()
        for path in files:
            try:
                stat = path.stat()
                size = stat.st_size
                mtime = stat.st_mtime
            except OSError:
                # File may have been deleted between scan and stat
                size = 0
                mtime = 0.0

            row_count = self._count_lines(path)
            entry = FileEntry(
                path=path,
                size=size,
                mtime=mtime,
                git_status=git_status.get(path),
                row_count=row_count,
            )
            # Restore cached blame data
            cached = self._blame_cache.get(path)
            if cached:
                entry.last_author = cached.last_author
                entry.last_git_modified = cached.last_modified
            self.entries[path] = entry

        # Deleted files are absent from the filesystem scan but still need rows
        # so their status and diff remain visible.
        deleted_statuses = {GitStatus.DELETED, GitStatus.STAGED_DELETED}
        for path, status in git_status.items():
            if status in deleted_statuses and path not in self.entries and path.is_relative_to(self.scanner.root):
                self.entries[path] = FileEntry(path=path, git_status=status)

        return list(self.entries.values())

    @staticmethod
    def _count_lines(path: Path) -> int | None:
        """Count lines in a text file. Returns None if binary."""
        try:
            data = path.read_bytes()[:8192]
            if b"\x00" in data:
                return None
            return path.read_text(errors="replace").count("\n")
        except OSError:
            return None

    def update_diff_stats(self, path: Path) -> FileEntry | None:
        """Populate diff stats for a single file. Called from background worker."""
        entry = self.entries.get(path)
        # Only compute diffs for tracked files with git status (avoids wasted work)
        if not entry or not entry.git_status:
            return None
        file_stats = self.git.get_file_stats(path)
        if file_stats:
            entry.lines_added = file_stats.lines_added
            entry.lines_removed = file_stats.lines_removed
        return entry

    def update_blame(self, path: Path) -> FileEntry | None:
        """Populate blame info for a single file. Called from background worker."""
        entry = self.entries.get(path)
        if not entry:
            return None
        info = self.git.get_blame_info(path)
        if info:
            entry.last_author = info.last_author
            entry.last_git_modified = info.last_modified
            self._blame_cache[path] = info
        return entry
