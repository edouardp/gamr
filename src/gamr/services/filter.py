"""Filtering service for file entries."""

from __future__ import annotations

from dataclasses import dataclass

from gamr.config import FUZZY_THRESHOLD
from gamr.models import FileEntry, GitStatus


@dataclass(frozen=True, slots=True)
class StatusFilter:
    """A named UI filter that matches one or more Git statuses."""

    id: str
    label: str
    statuses: frozenset[GitStatus]


STATUS_FILTERS = (
    StatusFilter(
        "modified",
        "M",
        frozenset(
            {
                GitStatus.MODIFIED,
                GitStatus.ADDED,
                GitStatus.DELETED,
                GitStatus.UNTRACKED,
                GitStatus.STAGED_MODIFIED,
                GitStatus.STAGED_ADDED,
                GitStatus.STAGED_DELETED,
            }
        ),
    ),
    StatusFilter("added", "A", frozenset({GitStatus.ADDED, GitStatus.STAGED_ADDED})),
    StatusFilter(
        "deleted",
        "D",
        frozenset({GitStatus.DELETED, GitStatus.STAGED_DELETED}),
    ),
    StatusFilter("untracked", "?", frozenset({GitStatus.UNTRACKED})),
    StatusFilter(
        "staged",
        "S",
        frozenset(
            {
                GitStatus.STAGED_MODIFIED,
                GitStatus.STAGED_ADDED,
                GitStatus.STAGED_DELETED,
            }
        ),
    ),
)
STATUS_FILTERS_BY_ID = {sf.id: sf for sf in STATUS_FILTERS}


def statuses_for_filter_ids(filter_ids: set[str]) -> set[GitStatus]:
    """Expand selected filter IDs into the Git statuses they match."""
    statuses: set[GitStatus] = set()
    for filter_id in filter_ids:
        sf = STATUS_FILTERS_BY_ID.get(filter_id)
        if sf is not None:
            statuses.update(sf.statuses)
    return statuses


def filter_ids_for_statuses(statuses: set[GitStatus]) -> set[str]:
    """Convert persisted legacy status values into explicit filter IDs."""
    filter_ids = {status_filter.id for status_filter in STATUS_FILTERS if status_filter.statuses.issubset(statuses)}
    legacy_filters = {
        GitStatus.MODIFIED: "modified",
        GitStatus.ADDED: "added",
        GitStatus.DELETED: "deleted",
        GitStatus.UNTRACKED: "untracked",
        GitStatus.STAGED_MODIFIED: "staged",
    }
    filter_ids.update(filter_id for status, filter_id in legacy_filters.items() if status in statuses)
    return filter_ids


def fuzzy_filter(entries: list[FileEntry], query: str) -> list[FileEntry]:
    """Filter entries using RapidFuzz partial ratio scoring."""
    from rapidfuzz import fuzz  # deferred: heavy C extension, only loaded when user filters

    query_lower = query.lower()
    scored = []
    for entry in entries:
        # Score against both filename and full path, take the better match
        name_score = fuzz.partial_ratio(query_lower, entry.name.lower())
        path_score = fuzz.partial_ratio(query_lower, str(entry.path).lower())
        score = max(name_score, path_score)
        # Threshold of 50 balances recall vs noise for partial matching
        if score >= FUZZY_THRESHOLD:
            scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [entry for _, entry in scored]


def filter_by_status(entries: list[FileEntry], statuses: set[GitStatus]) -> list[FileEntry]:
    """Filter entries to those matching given git statuses."""
    # Empty set means "no filter active" — show all files
    if not statuses:
        return entries
    return [e for e in entries if e.git_status in statuses]
