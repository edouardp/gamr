"""Tests for Toolbar status groups."""

from textual.app import App, ComposeResult

from gamr.models import GitStatus
from gamr.services.filter import filter_ids_for_statuses
from gamr.widgets.toolbar import Toolbar


class FilterApp(App):
    def compose(self) -> ComposeResult:
        yield Toolbar()


async def test_staged_filter_includes_all_staged_statuses() -> None:
    # Testing: the "staged" filter ID expands to all staged git statuses.
    # Input: selected_filter_ids set to {"staged"}.
    # Expected: active_statuses includes STAGED_MODIFIED, STAGED_ADDED, STAGED_DELETED.
    # Asserts: the filter group correctly maps one ID to multiple GitStatus values.
    app = FilterApp()
    async with app.run_test() as pilot:
        bar = app.query_one(Toolbar)

        bar.selected_filter_ids = {"staged"}
        await pilot.pause()

        assert bar.active_statuses == {
            GitStatus.STAGED_MODIFIED,
            GitStatus.STAGED_ADDED,
            GitStatus.STAGED_DELETED,
        }


async def test_added_filter_includes_staged_additions() -> None:
    # Testing: the "added" filter ID includes both unstaged and staged additions.
    # Input: selected_filter_ids set to {"added"}.
    # Expected: active_statuses includes ADDED and STAGED_ADDED.
    # Asserts: the "added" group covers all flavors of newly added files.
    app = FilterApp()
    async with app.run_test() as pilot:
        bar = app.query_one(Toolbar)

        bar.selected_filter_ids = {"added"}
        await pilot.pause()

        assert bar.active_statuses == {GitStatus.ADDED, GitStatus.STAGED_ADDED}


async def test_overlapping_filter_toggle_preserves_other_group() -> None:
    # Testing: removing one filter ID doesn't affect unrelated active filters.
    # Input: both "staged" and "added" active, then "added" removed.
    # Expected: only staged statuses remain in active_statuses.
    # Asserts: filter groups are independent — toggling one doesn't corrupt another.
    app = FilterApp()
    async with app.run_test() as pilot:
        bar = app.query_one(Toolbar)

        bar.selected_filter_ids = {"staged", "added"}
        await pilot.pause()
        # Remove "added", staged should remain
        bar.selected_filter_ids = {"staged"}
        await pilot.pause()

        assert bar.active_statuses == {
            GitStatus.STAGED_MODIFIED,
            GitStatus.STAGED_ADDED,
            GitStatus.STAGED_DELETED,
        }
        assert bar.selected_filter_ids == {"staged"}


async def test_toggle_modified() -> None:
    # Testing: toggle_modified enables/disables the "modified" filter group.
    # Input: call toggle_modified twice (ON then OFF).
    # Expected: first call adds "modified" with MODIFIED+UNTRACKED; second clears all.
    # Asserts: the toggle is idempotent and fully clears state on second press.
    app = FilterApp()
    async with app.run_test() as pilot:
        bar = app.query_one(Toolbar)

        bar.toggle_modified()
        await pilot.pause()
        assert bar.selected_filter_ids == {"modified"}
        assert GitStatus.MODIFIED in bar.active_statuses
        assert GitStatus.UNTRACKED in bar.active_statuses

        bar.toggle_modified()
        await pilot.pause()
        assert bar.selected_filter_ids == set()
        assert bar.active_statuses == set()


def test_legacy_statuses_are_migrated_to_filter_ids() -> None:
    # Testing: filter_ids_for_statuses converts legacy GitStatus sets to filter IDs.
    # Input: set of {ADDED, STAGED_MODIFIED} (old-style persisted state).
    # Expected: returns {"added", "staged"} (new-style filter IDs).
    # Asserts: the migration helper correctly maps raw statuses to their group IDs.
    assert filter_ids_for_statuses({GitStatus.ADDED, GitStatus.STAGED_MODIFIED}) == {"added", "staged"}
