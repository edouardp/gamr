"""Tests for FilterBar status groups."""

from textual.app import App, ComposeResult

from gamr.models import GitStatus
from gamr.services.filter import filter_ids_for_statuses
from gamr.widgets.filter_bar import FilterBar


class FilterApp(App):
    def compose(self) -> ComposeResult:
        yield FilterBar()


async def test_staged_filter_includes_all_staged_statuses() -> None:
    app = FilterApp()
    async with app.run_test() as pilot:
        bar = app.query_one(FilterBar)

        bar.selected_filter_ids = {"staged"}
        await pilot.pause()

        assert bar.active_statuses == {
            GitStatus.STAGED_MODIFIED,
            GitStatus.STAGED_ADDED,
            GitStatus.STAGED_DELETED,
        }


async def test_added_filter_includes_staged_additions() -> None:
    app = FilterApp()
    async with app.run_test() as pilot:
        bar = app.query_one(FilterBar)

        bar.selected_filter_ids = {"added"}
        await pilot.pause()

        assert bar.active_statuses == {GitStatus.ADDED, GitStatus.STAGED_ADDED}


async def test_overlapping_filter_toggle_preserves_other_group() -> None:
    app = FilterApp()
    async with app.run_test() as pilot:
        bar = app.query_one(FilterBar)

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
    app = FilterApp()
    async with app.run_test() as pilot:
        bar = app.query_one(FilterBar)

        bar.toggle_modified()
        await pilot.pause()
        assert bar.selected_filter_ids == {"modified"}
        assert bar.active_statuses == {GitStatus.MODIFIED}

        bar.toggle_modified()
        await pilot.pause()
        assert bar.selected_filter_ids == set()
        assert bar.active_statuses == set()


def test_legacy_statuses_are_migrated_to_filter_ids() -> None:
    assert filter_ids_for_statuses({GitStatus.ADDED, GitStatus.STAGED_MODIFIED}) == {"added", "staged"}
