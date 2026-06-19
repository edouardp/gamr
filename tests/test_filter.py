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
    entries = [_entry("a.py"), _entry("b.py", GitStatus.MODIFIED)]
    assert filter_by_status(entries, set()) == entries


def test_filter_by_status_matches() -> None:
    entries = [
        _entry("a.py", GitStatus.MODIFIED),
        _entry("b.py", GitStatus.UNTRACKED),
        _entry("c.py"),
    ]
    result = filter_by_status(entries, {GitStatus.MODIFIED})
    assert len(result) == 1
    assert result[0].name == "a.py"


def test_filter_by_status_multiple_statuses() -> None:
    entries = [
        _entry("a.py", GitStatus.MODIFIED),
        _entry("b.py", GitStatus.ADDED),
        _entry("c.py", GitStatus.UNTRACKED),
    ]
    result = filter_by_status(entries, {GitStatus.MODIFIED, GitStatus.ADDED})
    assert len(result) == 2


def test_statuses_for_filter_ids() -> None:
    result = statuses_for_filter_ids({"modified"})
    assert GitStatus.MODIFIED in result
    assert GitStatus.ADDED in result
    assert GitStatus.DELETED in result
    assert GitStatus.UNTRACKED in result


def test_statuses_for_filter_ids_unknown() -> None:
    assert statuses_for_filter_ids({"nonexistent"}) == set()


def test_filter_ids_for_statuses() -> None:
    result = filter_ids_for_statuses({GitStatus.UNTRACKED})
    assert "untracked" in result


def test_fuzzy_filter_exact_match() -> None:
    entries = [_entry("main.py"), _entry("utils.py"), _entry("test_main.py")]
    result = fuzzy_filter(entries, "main")
    assert len(result) >= 2
    assert result[0].name == "main.py"


def test_fuzzy_filter_substring_with_dot() -> None:
    entries = [_entry("app.py"), _entry("app.tsx"), _entry("readme.md")]
    result = fuzzy_filter(entries, ".py")
    assert all(e.name.endswith(".py") for e in result)


def test_fuzzy_filter_substring_with_slash() -> None:
    entries = [
        FileEntry(path=Path("/project/src/app.py")),
        FileEntry(path=Path("/project/tests/test.py")),
    ]
    result = fuzzy_filter(entries, "src/")
    assert len(result) == 1
    assert "src" in str(result[0].path)


def test_fuzzy_filter_no_match() -> None:
    entries = [_entry("foo.py")]
    result = fuzzy_filter(entries, "zzzzzzz")
    assert result == []
