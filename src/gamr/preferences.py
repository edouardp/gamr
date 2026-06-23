"""User preferences loaded from $XDG_CONFIG_HOME/gamr/preferences.toml."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from gamr.models import DiffMode

_PREFS_PATH = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "gamr" / "preferences.toml"

_DIFF_MODE_NAMES = {m.value: m for m in DiffMode}

_OVERVIEW_STYLES = ("line", "quadrant", "sextant", "braille", "off")

_LOGO_MODES = ("auto", "kitty", "sextant", "unicode", "text")


class Preferences:
    """User preferences with defaults."""

    def __init__(self) -> None:
        self.diff_modes: list[DiffMode] = list(DiffMode)
        self.overview_styles: list[str] = list(_OVERVIEW_STYLES)
        self.logo_mode: str = "auto"
        self.logo_text: str | None = None
        self.focus_color: str = "#6b21a8"

    @classmethod
    def load(cls) -> Preferences:
        prefs = cls()
        if not _PREFS_PATH.exists():
            return prefs
        try:
            data = tomllib.loads(_PREFS_PATH.read_text())
        except Exception:
            return prefs
        if "preview" in data and "diff_modes" in data["preview"]:
            raw = data["preview"]["diff_modes"]
            if isinstance(raw, list):
                modes = [_DIFF_MODE_NAMES[v] for v in raw if v in _DIFF_MODE_NAMES]
                if modes:
                    prefs.diff_modes = modes
        if "preview" in data and "overview_styles" in data["preview"]:
            raw = data["preview"]["overview_styles"]
            if isinstance(raw, list):
                styles = [s for s in raw if s in _OVERVIEW_STYLES]
                if styles:
                    prefs.overview_styles = styles
        if "logo" in data:
            logo = data["logo"]
            if "mode" in logo and logo["mode"] in _LOGO_MODES:
                prefs.logo_mode = logo["mode"]
            if "text" in logo and isinstance(logo["text"], str):
                prefs.logo_text = logo["text"]
        if "ui" in data:
            ui = data["ui"]
            if "focus_color" in ui and isinstance(ui["focus_color"], str):
                prefs.focus_color = ui["focus_color"]
        return prefs


#    🬖🬋🬏🬖🬋🬏🬱🬞🬓🬚🬋🬏 Git-aware
#    ▌🬋🬓🬛🬋▌▌🬄▌🬛🬚🬀 Agentic coding assistant
#    🬈🬋🬀🬄 🬄🬄 🬄🬄🬁🬃 Monitor & Review
