"""Diff parsing — converts unified diffs into structured data for rendering.

Pure functions with no UI dependencies. Used by PreviewPane for both
full-diff and gutter-diff rendering modes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DiffData:
    """Parsed diff data for a single file."""

    added_lines: set[int]  # 1-indexed source line numbers that were added
    changed_lines: set[int]  # 1-indexed lines that replaced removed lines (1:1 pairing)
    removed_context: dict[int, list[str]]  # line_num → removed lines shown above it
    trailing_removed: list[str]  # removed lines after the last source line


def parse_diff_hunks(diff_text: str | None) -> DiffData:
    """Parse unified diff into structured data.

    Removed lines are grouped as a block and attached to the next source line
    that follows them (or trailing if at end of file).
    """
    added_lines: set[int] = set()
    changed_lines: set[int] = set()
    removed_context: dict[int, list[str]] = {}
    pending_removed: list[str] = []

    if not diff_text:
        return DiffData(added_lines, changed_lines, removed_context, [])

    current_new_line = 0
    for dline in diff_text.splitlines():
        if dline.startswith("@@"):
            m = re.search(r"\+(\d+)", dline)
            if m:
                current_new_line = int(m.group(1)) - 1
                pending_removed = []
        elif dline.startswith("+") and not dline.startswith("+++"):
            current_new_line += 1
            added_lines.add(current_new_line)
            if pending_removed:
                changed_lines.add(current_new_line)
                # Attach entire removed block to the first added line after it
                removed_context[current_new_line] = pending_removed
                pending_removed = []
        elif dline.startswith("-") and not dline.startswith("---"):
            pending_removed.append(dline[1:])
        else:
            current_new_line += 1
            if pending_removed:
                removed_context[current_new_line] = pending_removed
                pending_removed = []

    return DiffData(added_lines, changed_lines, removed_context, pending_removed)


@dataclass(frozen=True, slots=True)
class GutterMarkers:
    """Line sets for gutter-mode rendering."""

    changed: set[int]
    pure_added: set[int]
    has_deletion_after: set[int]


def compute_gutter_markers(diff_text: str, total_lines: int) -> GutterMarkers:
    """Compute gutter markers from a unified diff.

    Returns:
        (changed, pure_added, has_deletion_after) — sets of 1-indexed line numbers.
    """
    data = parse_diff_hunks(diff_text)
    pure_added = data.added_lines - data.changed_lines
    has_deletion_after: set[int] = {
        ln - 1 for ln in data.removed_context if ln - 1 >= 1 and ln not in data.changed_lines
    }
    if data.trailing_removed and total_lines > 0:
        has_deletion_after.add(total_lines)
    return GutterMarkers(data.changed_lines, pure_added, has_deletion_after)
