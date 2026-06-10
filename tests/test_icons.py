"""Tests for IconResolver."""

from pathlib import Path

from gamr.services.icons import IconResolver


class TestIconResolverDefaults:
    def test_default_file_icon(self):
        resolver = IconResolver()
        icon = resolver.get_icon(Path("/some/unknown.xyz"))
        assert icon == "📄"

    def test_default_dir_icon(self):
        resolver = IconResolver()
        icon = resolver.get_icon(Path("/some/dir"), is_dir=True)
        assert icon == "📂"


class TestIconResolverLookup:
    def setup_method(self):
        self.resolver = IconResolver()
        self.resolver.name_icons = {"Makefile": "🔧", ".gitignore": "🙈"}
        self.resolver.ext_icons = {"py": "🐍", "rs": "🦀"}
        self.resolver.filetype_icons = {"dir": "📁", "file": "📃"}

    def test_name_match(self):
        assert self.resolver.get_icon(Path("/project/Makefile")) == "🔧"

    def test_extension_match(self):
        assert self.resolver.get_icon(Path("/src/main.py")) == "🐍"

    def test_name_priority_over_extension(self):
        # .gitignore has no extension but matches by name
        assert self.resolver.get_icon(Path("/project/.gitignore")) == "🙈"

    def test_filetype_dir_fallback(self):
        assert self.resolver.get_icon(Path("/unknown_dir"), is_dir=True) == "📁"

    def test_filetype_file_fallback(self):
        assert self.resolver.get_icon(Path("/unknown.xyz")) == "📃"


class TestParseSimple:
    def test_parses_yaml(self, tmp_path):
        icons_yaml = tmp_path / "icons.yaml"
        icons_yaml.write_text(
            "name:\n  Makefile: 🔧\n  Dockerfile: 🐳\nextension:\n  py: 🐍\n  rs: 🦀\nfiletype:\n  dir: 📁\n"
        )
        resolver = IconResolver.__new__(IconResolver)
        resolver.name_icons = {}
        resolver.ext_icons = {}
        resolver.filetype_icons = {}
        resolver._parse_simple(icons_yaml)
        assert resolver.name_icons == {"Makefile": "🔧", "Dockerfile": "🐳"}
        assert resolver.ext_icons == {"py": "🐍", "rs": "🦀"}
        assert resolver.filetype_icons == {"dir": "📁"}

    def test_skips_comments_and_blank_lines(self, tmp_path):
        icons_yaml = tmp_path / "icons.yaml"
        icons_yaml.write_text("# comment\n\nname:\n  foo: bar\n")
        resolver = IconResolver.__new__(IconResolver)
        resolver.name_icons = {}
        resolver.ext_icons = {}
        resolver.filetype_icons = {}
        resolver._parse_simple(icons_yaml)
        assert resolver.name_icons == {"foo": "bar"}

    def test_empty_file(self, tmp_path):
        icons_yaml = tmp_path / "icons.yaml"
        icons_yaml.write_text("")
        resolver = IconResolver.__new__(IconResolver)
        resolver.name_icons = {}
        resolver.ext_icons = {}
        resolver.filetype_icons = {}
        resolver._parse_simple(icons_yaml)
        assert resolver.name_icons == {}
