"""UI constants and configuration values.

All magic numbers and design tokens referenced by the UI are defined here
so they're easy to find and adjust. See docs/UI_DESIGN.md for the rationale
behind these values.
"""

# Gradient color ramp (256-color codes): cool → hot
# Applied to Size and Modified columns. See ADR-011.
GRADIENT_COLORS = [15, 51, 45, 39, 33, 27, 57, 93, 129, 165, 201, 200, 199, 198, 197, 196]

# Background colors for full-diff mode (hex)
DIFF_BG_ADDED = "#002200"
DIFF_BG_REMOVED = "#300000"

# Monokai theme background for the preview pane
PREVIEW_BG = "#272822"

# Padding width for diff backgrounds to fill the pane
DIFF_PAD_WIDTH = 200

# Fuzzy search score threshold (0-100). Files below this are excluded.
FUZZY_THRESHOLD = 70

# File watcher poll interval in seconds
WATCHER_POLL_INTERVAL = 0.5

# Relative timestamp refresh interval in seconds
TIMESTAMP_REFRESH_INTERVAL = 10

# Split handle constraints (fraction of total width)
SPLIT_MIN = 0.1
SPLIT_MAX = 0.9
