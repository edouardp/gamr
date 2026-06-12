"""Command palette provider for Gamr settings."""

from __future__ import annotations

from textual.command import Hit, Hits, Provider

from gamr.widgets.file_tree_table import FileTreeTable
from gamr.widgets.preview_pane import DiffOverview


class GamrCommands(Provider):
    """Command palette commands for Gamr settings.

    Textual's Provider protocol: search() yields Hit objects scored by fuzzy match.
    """

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)

        commands = [
            (
                "Toggle spaced paths (src / worker / foo.py)",
                self._toggle_spaced_paths,
                "Toggle spaces around / in flat path view",
            ),
            (
                "Toggle gradient colors on age column",
                self._toggle_gradient,
                "Color-code modification times by recency",
            ),
            (
                "Cycle diff overview style (line/braille/sextant)",
                self._cycle_overview_style,
                "Cycle between line, braille, and sextant overview bar",
            ),
        ]
        for label, callback, help_text in commands:
            score = matcher.match(label)
            if score > 0:
                yield Hit(score, label, callback, help=help_text)

    def _toggle_spaced_paths(self) -> None:
        tree = self.app.query_one(FileTreeTable)
        tree.spaced_paths = not tree.spaced_paths

    def _toggle_gradient(self) -> None:
        tree = self.app.query_one(FileTreeTable)
        tree.gradient_colors = not tree.gradient_colors

    def _cycle_overview_style(self) -> None:
        overview = self.app.query_one(DiffOverview)
        if overview.use_sextant:
            # sextant → line
            overview.use_sextant = False
            overview.use_braille = False
        elif overview.use_braille:
            # braille → sextant
            overview.use_braille = False
            overview.use_sextant = True
        else:
            # line → braille
            overview.use_braille = True
