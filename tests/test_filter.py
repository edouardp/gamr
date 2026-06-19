"""Tests for filter service."""

from pathlib import Path

from gamr.models import FileEntry, GitStatus
from gamr.services.filter import (
    filter_by_status,
    filter_ids_for_statuses,
    fuzzy_filter,
    statuses_for_filter_ids,
)


def _entry(name: str, status: GitStatus | None = None) -> FileEntry:
    return FileEntry(path=Path(f"/project/{name}"), git_status=status)


def test_filter_by_status_empty_set_returns_all() -> None:
    # Testing: filter_by_status with an empty status set (no filter active).
    # Input: two entries (one with status, one without), empty filter set.
    # Expected: all entries returned unchanged — empty set means "show everything".
    # Asserts: the "no filter" path doesn't accidentally hide files.
    entries = [_entry("a.py"), _entry("b.py", GitStatus.MODIFIED)]
    assert filter_by_status(entries, set()) == entries


def test_filter_by_status_matches() -> None:
    # Testing: filter_by_status correctly includes only matching entries.
    # Input: 3 entries with different statuses, filter for MODIFIED only.
    # Expected: only "a.py" (MODIFIED) returned; UNTRACKED and None excluded.
    # Asserts: exact status matching — doesn't include unrelated statuses.
    entries = [
        _entry("a.py", GitStatus.MODIFIED),
        _entry("b.py", GitStatus.UNTRACKED),
        _entry("c.py"),
    ]
    result = filter_by_status(entries, {GitStatus.MODIFIED})
    assert len(result) == 1
    assert result[0].name == "a.py"


def test_filter_by_status_multiple_statuses() -> None:
    # Testing: filter_by_status with multiple statuses in the filter set.
    # Input: 3 entries (MODIFIED, ADDED, UNTRACKED), filter for {MODIFIED, ADDED}.
    # Expected: 2 entries returned (MODIFIED + ADDED), UNTRACKED excluded.
    # Asserts: OR semantics — entry matches if its status is in the set.
    entries = [
        _entry("a.py", GitStatus.MODIFIED),
        _entry("b.py", GitStatus.ADDED),
        _entry("c.py", GitStatus.UNTRACKED),
    ]
    result = filter_by_status(entries, {GitStatus.MODIFIED, GitStatus.ADDED})
    assert len(result) == 2


def test_statuses_for_filter_ids() -> None:
    # Testing: statuses_for_filter_ids expands the "modified" filter ID into all
    # git statuses it represents.
    # Input: {"modified"} filter ID.
    # Expected: includes MODIFIED, ADDED, DELETED, UNTRACKED (the broad "changed" set).
    # Asserts: the "modified" UI filter captures all files that would appear in git status.
    result = statuses_for_filter_ids({"modified"})
    assert GitStatus.MODIFIED in result
    assert GitStatus.ADDED in result
    assert GitStatus.DELETED in result
    assert GitStatus.UNTRACKED in result


def test_statuses_for_filter_ids_unknown() -> None:
    # Testing: statuses_for_filter_ids with an unrecognized filter ID.
    # Input: {"nonexistent"} — not a valid filter.
    # Expected: empty set — unknown filters are silently ignored.
    # Asserts: no crash, no garbage statuses leaked.
    assert statuses_for_filter_ids({"nonexistent"}) == set()


def test_filter_ids_for_statuses() -> None:
    # Testing: filter_ids_for_statuses converts a raw GitStatus into the UI filter
    # IDs that would match it (reverse lookup).
    # Input: {GitStatus.UNTRACKED}.
    # Expected: "untracked" is in the result.
    # Asserts: the round-trip from status → filter ID works for state persistence.
    result = filter_ids_for_statuses({GitStatus.UNTRACKED})
    assert "untracked" in result


def test_fuzzy_filter_exact_match() -> None:
    # Testing: fuzzy_filter scores exact name matches highest.
    # Input: 3 files, query "main".
    # Expected: "main.py" ranked first (exact match), "test_main.py" also included.
    # Asserts: RapidFuzz partial_ratio scoring ranks exact matches above partial.
    entries = [_entry("main.py"), _entry("utils.py"), _entry("test_main.py")]
    result = fuzzy_filter(entries, "main")
    assert len(result) >= 2
    assert result[0].name == "main.py"


def test_fuzzy_filter_substring_with_dot() -> None:
    # Testing: fuzzy_filter falls back to literal substring matching when query
    # contains a dot (indicating a file extension pattern).
    # Input: 3 files, query ".py".
    # Expected: only .py files returned (exact substring, not fuzzy).
    # Asserts: the dot-detection optimization avoids false positives from fuzzy scoring.
    entries = [_entry("app.py"), _entry("app.tsx"), _entry("readme.md")]
    result = fuzzy_filter(entries, ".py")
    assert all(e.name.endswith(".py") for e in result)


def test_fuzzy_filter_substring_with_slash() -> None:
    # Testing: fuzzy_filter uses literal substring matching when query contains a
    # slash (indicating a path fragment).
    # Input: 2 files in different dirs, query "src/".
    # Expected: only the file under src/ matches.
    # Asserts: slash-detection matches against the full path, not just the filename.
    entries = [
        FileEntry(path=Path("/project/src/app.py")),
        FileEntry(path=Path("/project/tests/test.py")),
    ]
    result = fuzzy_filter(entries, "src/")
    assert len(result) == 1
    assert "src" in str(result[0].path)


def test_fuzzy_filter_no_match() -> None:
    # Testing: fuzzy_filter returns empty list when no file scores above threshold.
    # Input: one file "foo.py", query "zzzzzzz" (no similarity).
    # Expected: empty list — score below FUZZY_THRESHOLD (70).
    # Asserts: low-scoring results are correctly filtered out.
    entries = [_entry("foo.py")]
    result = fuzzy_filter(entries, "zzzzzzz")
    assert result == []
