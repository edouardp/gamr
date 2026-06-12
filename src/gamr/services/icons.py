"""Icon resolver using lsd config files."""

from __future__ import annotations

import os
from pathlib import Path

_LSD_CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "lsd"


class IconResolver:
    """Resolves file/dir icons from lsd icons.yaml config."""

    def __init__(self) -> None:
        self.name_icons: dict[str, str] = {}
        self.ext_icons: dict[str, str] = {}
        self.filetype_icons: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        icons_file = _LSD_CONFIG_DIR / "icons.yaml"
        if not icons_file.exists():
            return
        try:
            import yaml
        except ImportError:
            # PyYAML is optional; fall back to hand-rolled parser for simple flat YAML
            self._parse_simple(icons_file)
            return
        with open(icons_file) as f:
            data = yaml.safe_load(f)
        if not data:
            return
        self.name_icons = {str(k): str(v) for k, v in (data.get("name") or {}).items()}
        self.ext_icons = {str(k): str(v) for k, v in (data.get("extension") or {}).items()}
        self.filetype_icons = {str(k): str(v) for k, v in (data.get("filetype") or {}).items()}

    def _parse_simple(self, path: Path) -> None:
        """Parse lsd icons.yaml without PyYAML dependency."""
        section = None
        for line in path.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            # Detect top-level keys by absence of leading whitespace
            if not line.startswith(" ") and stripped.endswith(":"):
                section = stripped[:-1]
                continue
            if section and ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if section == "name":
                    self.name_icons[key] = val
                elif section == "extension":
                    self.ext_icons[key] = val
                elif section == "filetype":
                    self.filetype_icons[key] = val

    def get_icon(self, path: Path, is_dir: bool = False) -> str:
        """Get icon for a file/directory path. Priority: name > extension > filetype."""
        name = path.name
        # Exact name match first
        if name in self.name_icons:
            return self._pad(self.name_icons[name])
        # Extension match
        ext = path.suffix.lstrip(".")
        if ext and ext in self.ext_icons:
            return self._pad(self.ext_icons[ext])
        # Filetype fallback
        if is_dir:
            return self._pad(self.filetype_icons.get("dir", "📂"))
        return self._pad(self.filetype_icons.get("file", "📄"))

    @staticmethod
    def _pad(icon: str) -> str:
        """Prefix single-width icons with a space so text aligns."""
        import unicodedata

        width = sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in icon)
        return f" {icon}" if width == 1 else icon
