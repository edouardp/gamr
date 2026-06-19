"""Tests for persistent app state."""

import json
from pathlib import Path

from gamr.state import AppState


def test_invalid_semantic_state_falls_back_to_defaults(tmp_path: Path, monkeypatch) -> None:
    # Testing: AppState.load handles invalid enum values in persisted state.
    # Input: state file with view_mode="invalid" and active_statuses=["also-invalid"].
    # Expected: defaults applied — view_mode="tree", active_filter_ids=empty set.
    # Asserts: corrupted state doesn't crash the app; graceful fallback to defaults.
    state_file = tmp_path / ".gamrstate"
    state_file.write_text(
        json.dumps(
            {
                "target": str(tmp_path.resolve()),
                "view_mode": "invalid",
                "active_statuses": ["also-invalid"],
            }
        )
    )

    state = AppState.load(tmp_path)

    assert state.view_mode.value == "tree"
    assert state.active_filter_ids == set()


def test_non_object_state_falls_back_to_defaults(tmp_path: Path, monkeypatch) -> None:
    # Testing: AppState.load handles non-object JSON (e.g., a JSON array).
    # Input: state file containing "[]" (valid JSON but wrong type).
    # Expected: defaults applied — view_mode="tree".
    # Asserts: unexpected JSON structures don't crash deserialization.
    state_file = tmp_path / ".gamrstate"
    state_file.write_text("[]")

    state = AppState.load(tmp_path)

    assert state.view_mode.value == "tree"


def test_state_migrates_legacy_statuses_to_filter_ids(tmp_path: Path) -> None:
    # Testing: AppState.from_dict migrates old "active_statuses" format to "active_filters".
    # Input: dict with active_statuses=["M"] (legacy format).
    # Expected: active_filter_ids={"modified"}, serialized as active_filters; no active_statuses key.
    # Asserts: old persisted state is transparently upgraded to the new filter ID scheme.
    state = AppState.from_dict(
        tmp_path,
        {
            "target": str(tmp_path.resolve()),
            "active_statuses": ["M"],
        },
    )

    assert state is not None
    assert state.active_filter_ids == {"modified"}
    assert state.to_dict()["active_filters"] == ["modified"]
    assert "active_statuses" not in state.to_dict()
