"""Tests for IconResolver."""

from pathlib import Path

from gamr.services.icons import IconResolver


class TestIconResolverDefaults:
    def test_default_file_icon(self):
        # Testing: fallback icon for an unknown file extension.
        # Input: path with unrecognized ".xyz" extension, no custom icons loaded.
        # Expected: returns "📄" (default file icon).
        # Asserts: the resolver always returns a valid icon even for unknown types.
        resolver = IconResolver()
        icon = resolver.get_icon(Path("/some/unknown.xyz"))
        assert icon == "📄"

    def test_default_dir_icon(self):
        # Testing: fallback icon for a directory.
        # Input: path with is_dir=True, no custom icons loaded.
        # Expected: returns "📂" (default directory icon).
        # Asserts: directories get a distinct default icon from files.
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
        # Testing: icon resolution by exact filename match.
        # Input: path ending in "Makefile" (registered in name_icons).
        # Expected: returns "🔧".
        # Asserts: name-based lookup takes priority and returns the correct icon.
        assert self.resolver.get_icon(Path("/project/Makefile")) == "🔧"

    def test_extension_match(self):
        # Testing: icon resolution by file extension.
        # Input: path with ".py" extension (registered in ext_icons).
        # Expected: returns "🐍".
        # Asserts: extension-based lookup works for known extensions.
        assert self.resolver.get_icon(Path("/src/main.py")) == "🐍"

    def test_name_priority_over_extension(self):
        # Testing: name match takes priority over extension match.
        # Input: ".gitignore" which matches by name (no real extension).
        # Expected: returns "🙈" (name icon, not extension fallback).
        # Asserts: the resolution order is name → extension → filetype.
        # .gitignore has no extension but matches by name
        assert self.resolver.get_icon(Path("/project/.gitignore")) == "🙈"

    def test_filetype_dir_fallback(self):
        # Testing: filetype fallback for directories when no name/ext match.
        # Input: unknown directory path with is_dir=True.
        # Expected: returns "📁" (filetype "dir" icon).
        # Asserts: the filetype layer provides a typed fallback before the hard default.
        assert self.resolver.get_icon(Path("/unknown_dir"), is_dir=True) == "📁"

    def test_filetype_file_fallback(self):
        # Testing: filetype fallback for files when no name/ext match.
        # Input: unknown file with unrecognized extension.
        # Expected: returns "📃" (filetype "file" icon).
        # Asserts: filetype fallback differentiates files from the hard-coded default.
        assert self.resolver.get_icon(Path("/unknown.xyz")) == "📃"


class TestParseSimple:
    def test_parses_yaml(self, tmp_path):
        # Testing: _parse_simple correctly parses a well-formed icons.yaml file.
        # Input: YAML file with name, extension, and filetype sections.
        # Expected: each section populates the corresponding dict on the resolver.
        # Asserts: the simple YAML parser handles all three icon categories.
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
        # Testing: the parser ignores comments (#) and blank lines in YAML.
        # Input: YAML with a comment line, a blank line, then a valid entry.
        # Expected: only "foo: bar" parsed into name_icons.
        # Asserts: non-data lines don't corrupt or interrupt parsing.
        icons_yaml = tmp_path / "icons.yaml"
        icons_yaml.write_text("# comment\n\nname:\n  foo: bar\n")
        resolver = IconResolver.__new__(IconResolver)
        resolver.name_icons = {}
        resolver.ext_icons = {}
        resolver.filetype_icons = {}
        resolver._parse_simple(icons_yaml)
        assert resolver.name_icons == {"foo": "bar"}

    def test_empty_file(self, tmp_path):
        # Testing: _parse_simple handles an empty icons file gracefully.
        # Input: empty icons.yaml file.
        # Expected: all icon dicts remain empty, no crash.
        # Asserts: the parser doesn't error on missing content.
        icons_yaml = tmp_path / "icons.yaml"
        icons_yaml.write_text("")
        resolver = IconResolver.__new__(IconResolver)
        resolver.name_icons = {}
        resolver.ext_icons = {}
        resolver.filetype_icons = {}
        resolver._parse_simple(icons_yaml)
        assert resolver.name_icons == {}
