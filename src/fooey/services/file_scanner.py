"""File scanning service with watchdog and polling fallback."""

from __future__ import annotations

import fnmatch
import os
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from queue import Empty, Queue
from typing import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer


class ChangeType(Enum):
    CREATED = "created"
    DELETED = "deleted"
    MODIFIED = "modified"


@dataclass(frozen=True, slots=True)
class FileChange:
    path: Path
    change_type: ChangeType


class FileScanner:
    """Recursively scans a directory and emits change events."""

    def __init__(self, root: Path, ignore_patterns: list[str] | None = None) -> None:
        self.root = root.resolve()
        self.ignore_patterns = ignore_patterns or self._default_ignores()
        self.queue: Queue[FileChange] = Queue()
        self._observer: Observer | None = None
        self._polling = False
        self._poll_snapshot: dict[Path, float] = {}

    def scan(self) -> list[Path]:
        """Return all files under root, respecting ignore patterns."""
        files: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            # Prune ignored dirs in-place
            dirnames[:] = [
                d for d in dirnames if not self._is_ignored(Path(dirpath) / d)
            ]
            for f in filenames:
                p = Path(dirpath) / f
                if not self._is_ignored(p):
                    files.append(p)
        return files

    def start_watching(self) -> None:
        """Start filesystem watching. Falls back to polling on failure."""
        try:
            handler = _Handler(self.root, self.queue, self._is_ignored)
            self._observer = Observer()
            self._observer.schedule(handler, str(self.root), recursive=True)
            self._observer.start()
        except Exception:
            self._polling = True
            self._poll_snapshot = self._build_snapshot()

    def stop(self) -> None:
        """Stop watching."""
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._observer = None

    def poll_changes(self) -> None:
        """If using polling fallback, check for changes now."""
        if not self._polling:
            return
        new_snapshot = self._build_snapshot()
        old = self._poll_snapshot
        for p, mtime in new_snapshot.items():
            if p not in old:
                self.queue.put(FileChange(p, ChangeType.CREATED))
            elif mtime != old[p]:
                self.queue.put(FileChange(p, ChangeType.MODIFIED))
        for p in old:
            if p not in new_snapshot:
                self.queue.put(FileChange(p, ChangeType.DELETED))
        self._poll_snapshot = new_snapshot

    def drain(self) -> list[FileChange]:
        """Drain all pending change events from the queue."""
        changes: list[FileChange] = []
        while True:
            try:
                changes.append(self.queue.get_nowait())
            except Empty:
                break
        return changes

    def _build_snapshot(self) -> dict[Path, float]:
        snap: dict[Path, float] = {}
        for f in self.scan():
            try:
                snap[f] = f.stat().st_mtime
            except OSError:
                pass
        return snap

    def _is_ignored(self, path: Path) -> bool:
        rel = str(path.relative_to(self.root))
        name = path.name
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(rel, pattern):
                return True
        return False

    @staticmethod
    def _default_ignores() -> list[str]:
        return [
            ".git",
            "__pycache__",
            "*.pyc",
            ".DS_Store",
            "node_modules",
            ".venv",
            "venv",
        ]

    def load_gitignore(self) -> None:
        """Load additional patterns from .gitignore if present."""
        gitignore = self.root / ".gitignore"
        if gitignore.exists():
            for line in gitignore.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    self.ignore_patterns.append(line)


class _Handler(FileSystemEventHandler):
    """Bridges watchdog thread events to our queue."""

    def __init__(
        self,
        root: Path,
        queue: Queue[FileChange],
        is_ignored: Callable[[Path], bool],
    ) -> None:
        self._root = root
        self._queue = queue
        self._is_ignored = is_ignored

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            p = Path(event.src_path)
            if not self._is_ignored(p):
                self._queue.put(FileChange(p, ChangeType.CREATED))

    def on_deleted(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            p = Path(event.src_path)
            if not self._is_ignored(p):
                self._queue.put(FileChange(p, ChangeType.DELETED))

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            p = Path(event.src_path)
            if not self._is_ignored(p):
                self._queue.put(FileChange(p, ChangeType.MODIFIED))
