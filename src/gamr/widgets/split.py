"""Resizable horizontal split container."""

from __future__ import annotations

from textual.containers import Horizontal
from textual.events import MouseDown, MouseMove, MouseUp
from textual.reactive import reactive
from textual.widget import Widget

from gamr.config import SPLIT_MAX, SPLIT_MIN


class SplitHandle(Widget):
    """Draggable divider between two panes."""

    ALLOW_SELECT = False

    DEFAULT_CSS = """
    SplitHandle {
        width: 1;
        height: 100%;
        background: $surface-lighten-1;
    }
    SplitHandle:hover {
        background: $surface-lighten-2;
    }
    SplitHandle.-dragging {
        background: $surface-lighten-2;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._dragging = False

    def render(self) -> str:
        return ""

    def on_mouse_down(self, event: MouseDown) -> None:
        self._dragging = True
        self.add_class("-dragging")
        # Capture mouse so we get move events even when cursor leaves the handle
        self.capture_mouse()
        event.stop()

    def on_mouse_up(self, event: MouseUp) -> None:
        self._dragging = False
        self.remove_class("-dragging")
        self.release_mouse()
        event.stop()

    def on_mouse_move(self, event: MouseMove) -> None:
        if self._dragging:
            parent = self.parent
            if isinstance(parent, HorizontalSplit):
                parent.handle_drag(event.screen_x)
            event.stop()


class HorizontalSplit(Horizontal):
    """A horizontal container with a draggable split handle."""

    ALLOW_SELECT = False

    split_fraction = reactive(0.5)

    DEFAULT_CSS = """
    HorizontalSplit {
        height: 1fr;
    }
    """

    def on_mount(self) -> None:
        self._apply_split()

    def handle_drag(self, screen_x: int) -> None:
        """Update split fraction based on drag position."""
        region = self.content_region
        if region.width <= 1:
            return
        # Convert screen x to relative position within this widget
        local_x = screen_x - region.x
        fraction = local_x / region.width
        # Clamp so neither pane can be fully collapsed
        self.split_fraction = max(SPLIT_MIN, min(SPLIT_MAX, fraction))

    def watch_split_fraction(self, value: float) -> None:
        self._apply_split()

    def _apply_split(self) -> None:
        """Apply the split fraction to child widths using fr units."""
        children = list(self.children)
        # Layout: [left_pane, SplitHandle (1 col fixed), right_pane]
        if len(children) == 3:
            left, handle, right = children
            # fr units divide remaining space after the fixed-width handle
            left_fr = int(self.split_fraction * 100)
            right_fr = int((1 - self.split_fraction) * 100)
            left.styles.width = f"{left_fr}fr"
            right.styles.width = f"{right_fr}fr"
