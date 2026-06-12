"""File scanning service with watchdog and polling fallback.

Two watchers:
- _Handler: watches the project tree for file creates/deletes/modifies (respects .gitignore)
- _GitHandler: watches .git/ for index/HEAD changes (detects commits, stages, resets)

Both emit FileChange events into a shared queue. The app's poll loop drains the queue
and classifies events as file changes vs git state changes.
"""

from __future__ import annotations

import fnmatch
import os
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from queue import Empty, Queue
from typing import Protocol

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer


class IgnoreFilter(Protocol):
    """Protocol for gitignore-style filters."""

    def is_ignored(self, path: str) -> bool | None: ...


class ChangeType(Enum):
    CREATED = "created"
    DELETED = "deleted"
    MODIFIED = "modified"
    GIT_STATE_CHANGED = "git_state_changed"


@dataclass(frozen=True, slots=True)
class FileChange:
    path: Path
    change_type: ChangeType


class FileScanner:
    """Recursively scans a directory and emits change events."""

    def __init__(
        self, root: Path, ignore_patterns: list[str] | None = None, ignore_filter: IgnoreFilter | None = None
    ) -> None:
        self.root = root.resolve()
        self.ignore_patterns = ignore_patterns if ignore_patterns is not None else self._default_ignores()
        self._ignore_filter: IgnoreFilter | None = ignore_filter
        self.queue: Queue[FileChange] = Queue()
        self._observer: Observer | None = None
        self._polling = False
        self._poll_snapshot: dict[Path, float] = {}

    def scan(self) -> list[Path]:
        """Return all files under root, respecting ignore patterns."""
        files: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            # Mutating dirnames in-place prevents os.walk from descending into ignored dirs
            dirnames[:] = [d for d in dirnames if not self._is_ignored(Path(dirpath) / d)]
            for f in filenames:
                p = Path(dirpath) / f
                if not self._is_ignored(p):
                    files.append(p)
        return files

    def start_watching(self, git_root: Path | None = None) -> None:
        """Start filesystem watching. Falls back to polling on failure."""
        try:
            handler = _Handler(self.root, self.queue, self._is_ignored)
            self._observer = Observer()
            self._observer.schedule(handler, str(self.root), recursive=True)
            if git_root and git_root.exists():
                git_handler = _GitHandler(self.queue)
                self._observer.schedule(git_handler, str(git_root), recursive=False)
            self._observer.start()
        except Exception:
            # watchdog may fail on some filesystems (network mounts, etc.)
            pass
        # Always enable polling as supplemental — native watchers may silently
        # miss events on BSD (kqueue) or Linux (inotify watch limits)
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
        rel = path.relative_to(self.root).as_posix()
        name = path.name
        # Two-layer filtering: hardcoded patterns (fast, always present) then .gitignore rules
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(rel, pattern):
                return True
        if self._ignore_filter is not None:
            result = self._ignore_filter.is_ignored(rel)
            if result:
                return True
        return False

    @staticmethod
    def _default_ignores() -> list[str]:
        return [
            ".git",
            "__pycache__",
            "*.pyc",
            ".DS_Store",
            ".gamrstate",
            "node_modules",
            ".venv",
            "venv",
        ]


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

    def _emit(self, event: FileSystemEvent, change_type: ChangeType) -> None:
        if not event.is_directory:
            p = Path(event.src_path)
            if not self._is_ignored(p):
                self._queue.put(FileChange(p, change_type))

    def on_created(self, event: FileSystemEvent) -> None:
        self._emit(event, ChangeType.CREATED)

    def on_deleted(self, event: FileSystemEvent) -> None:
        self._emit(event, ChangeType.DELETED)

    def on_modified(self, event: FileSystemEvent) -> None:
        self._emit(event, ChangeType.MODIFIED)

    def on_moved(self, event: FileSystemEvent) -> None:
        # A single directory move event is enough to trigger the app's full rescan.
        source = Path(event.src_path)
        destination = Path(event.dest_path)
        if not self._is_ignored(source):
            self._queue.put(FileChange(source, ChangeType.DELETED))
        if not self._is_ignored(destination):
            self._queue.put(FileChange(destination, ChangeType.CREATED))


class _GitHandler(FileSystemEventHandler):
    """Watches .git directory for state changes (commits, stages, resets)."""

    _GIT_STATE_FILES = {"index", "HEAD", "COMMIT_EDITMSG"}

    def __init__(self, queue: Queue[FileChange]) -> None:
        self._queue = queue

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        name = Path(event.src_path).name
        if name in self._GIT_STATE_FILES:
            self._queue.put(FileChange(Path(event.src_path), ChangeType.GIT_STATE_CHANGED))
