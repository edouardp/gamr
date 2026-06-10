"""Tests for persistent app state."""

import json
from pathlib import Path

from gamr.state import AppState


def test_invalid_semantic_state_falls_back_to_defaults(tmp_path: Path, monkeypatch) -> None:
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
    state_file = tmp_path / ".gamrstate"
    state_file.write_text("[]")

    state = AppState.load(tmp_path)

    assert state.view_mode.value == "tree"


def test_state_migrates_legacy_statuses_to_filter_ids(tmp_path: Path) -> None:
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
