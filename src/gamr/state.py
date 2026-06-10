"""Persistent app state management."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from gamr.models import DiffMode, GitStatus
from gamr.services.filter import STATUS_FILTERS_BY_ID, filter_ids_for_statuses
from gamr.widgets.file_tree_table import ViewMode

if TYPE_CHECKING:
    from gamr.widgets.file_tree_table import FileTreeTable
    from gamr.widgets.filter_bar import FilterBar
    from gamr.widgets.split import HorizontalSplit

_TREE_SETTING_NAMES = (
    "view_mode",
    "show_status",
    "show_lines",
    "show_size",
    "show_mtime",
    "show_author",
    "show_git_time",
    "spaced_paths",
    "gradient_colors",
)


def _read_bool(data: dict[str, Any], key: str, default: bool) -> bool:
    """Read a strictly typed boolean from serialized state."""
    value = data.get(key, default)
    if not isinstance(value, bool):
        raise TypeError
    return value


@dataclass
class AppState:
    """Persists and restores app state between sessions."""

    target_path: Path
    view_mode: ViewMode = ViewMode.TREE
    diff_mode: DiffMode = DiffMode.FULL
    show_status: bool = True
    show_lines: bool = True
    show_size: bool = True
    show_mtime: bool = True
    show_author: bool = False
    show_git_time: bool = False
    spaced_paths: bool = True
    gradient_colors: bool = True
    collapsed_dirs: set[str] = field(default_factory=set)
    split_fraction: float = 0.5
    selected_path: str | None = None
    active_filter_ids: set[str] = field(default_factory=set)
    search_query: str = ""

    def __post_init__(self) -> None:
        self.target_path = self.target_path.resolve()

    @classmethod
    def load(cls, target_path: Path) -> AppState:
        """Load valid state for a target path, otherwise return defaults."""
        default = cls(target_path)
        state_file = target_path / ".gamrstate"
        if not state_file.exists():
            return default
        try:
            data = json.loads(state_file.read_text())
        except (json.JSONDecodeError, OSError):
            return default
        return cls.from_dict(target_path, data) or default

    def save(self) -> None:
        """Persist current state to .gamrstate in the target directory."""
        state_file = self.target_path / ".gamrstate"
        state_file.write_text(json.dumps(self.to_dict(), indent=2))

    def to_dict(self) -> dict[str, Any]:
        """Serialize state into its stable JSON representation."""
        return {
            "target": str(self.target_path),
            "view_mode": self.view_mode.value,
            "diff_mode": self.diff_mode.value,
            "show_status": self.show_status,
            "show_lines": self.show_lines,
            "show_size": self.show_size,
            "show_mtime": self.show_mtime,
            "show_author": self.show_author,
            "show_git_time": self.show_git_time,
            "spaced_paths": self.spaced_paths,
            "gradient_colors": self.gradient_colors,
            "collapsed_dirs": sorted(self.collapsed_dirs),
            "split_fraction": self.split_fraction,
            "selected_path": self.selected_path,
            "active_filters": sorted(self.active_filter_ids),
            "search_query": self.search_query,
        }

    @classmethod
    def from_dict(cls, target_path: Path, data: object) -> AppState | None:
        """Parse and validate serialized state for a target path."""
        if not isinstance(data, dict):
            return None

        resolved_target = target_path.resolve()
        if data.get("target") != str(resolved_target):
            return None

        try:
            view_mode = ViewMode(data.get("view_mode", "tree"))
            raw_diff = data.get("diff_mode", "gutter")
            try:
                diff_mode = DiffMode(raw_diff)
            except ValueError:
                diff_mode = DiffMode.GUTTER
            collapsed_data = data.get("collapsed_dirs", [])
            if not isinstance(collapsed_data, list):
                raise TypeError
            collapsed_dirs = set(collapsed_data)
            if not all(isinstance(path, str) for path in collapsed_dirs):
                raise TypeError
            active_filter_ids = cls._parse_active_filter_ids(data)
            split_fraction = float(data.get("split_fraction", 0.5))
            if not math.isfinite(split_fraction):
                raise ValueError
            selected_path = data.get("selected_path")
            search_query = data.get("search_query", "")
            if selected_path is not None and not isinstance(selected_path, str):
                raise TypeError
            if not isinstance(search_query, str):
                raise TypeError
            show_status = _read_bool(data, "show_status", True)
            show_lines = _read_bool(data, "show_lines", True)
            show_size = _read_bool(data, "show_size", True)
            show_mtime = _read_bool(data, "show_mtime", True)
            show_author = _read_bool(data, "show_author", False)
            show_git_time = _read_bool(data, "show_git_time", False)
            spaced_paths = _read_bool(data, "spaced_paths", True)
            gradient_colors = _read_bool(data, "gradient_colors", True)
        except (TypeError, ValueError):
            return None

        return cls(
            target_path=resolved_target,
            view_mode=view_mode,
            diff_mode=diff_mode,
            show_status=show_status,
            show_lines=show_lines,
            show_size=show_size,
            show_mtime=show_mtime,
            show_author=show_author,
            show_git_time=show_git_time,
            spaced_paths=spaced_paths,
            gradient_colors=gradient_colors,
            collapsed_dirs=collapsed_dirs,
            split_fraction=max(0.1, min(0.9, split_fraction)),
            selected_path=selected_path,
            active_filter_ids=active_filter_ids,
            search_query=search_query,
        )

    @staticmethod
    def _parse_active_filter_ids(data: dict[str, Any]) -> set[str]:
        """Parse explicit filter IDs or migrate the legacy status representation."""
        if "active_filters" in data:
            filter_data = data["active_filters"]
            if not isinstance(filter_data, list) or not all(isinstance(filter_id, str) for filter_id in filter_data):
                raise TypeError
            filter_ids = set(filter_data)
            if not filter_ids.issubset(STATUS_FILTERS_BY_ID):
                raise ValueError
            return filter_ids

        status_data = data.get("active_statuses", [])
        if not isinstance(status_data, list):
            raise TypeError
        return filter_ids_for_statuses({GitStatus(value) for value in status_data})

    def apply_to_widgets(
        self,
        tree: FileTreeTable,
        filter_bar: FilterBar,
        split: HorizontalSplit,
    ) -> None:
        """Apply persisted widget settings through their public APIs."""
        for setting_name in _TREE_SETTING_NAMES:
            setattr(tree, setting_name, getattr(self, setting_name))
        filter_bar.restore_state(set(self.active_filter_ids), self.search_query)
        split.split_fraction = self.split_fraction

    def capture_from_widgets(
        self,
        tree: FileTreeTable,
        filter_bar: FilterBar,
        split: HorizontalSplit,
        *,
        diff_mode: DiffMode,
        selected_path: Path | None,
    ) -> None:
        """Capture persistent values from live widgets."""
        for setting_name in _TREE_SETTING_NAMES:
            setattr(self, setting_name, getattr(tree, setting_name))
        self.diff_mode = diff_mode
        self.collapsed_dirs = tree.get_collapsed_dirs()
        self.split_fraction = split.split_fraction
        self.selected_path = str(selected_path) if selected_path else None
        self.active_filter_ids = set(filter_bar.selected_filter_ids)
        self.search_query = filter_bar.search_query
