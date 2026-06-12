# UI Design Rules

## Navigation

- **↑/↓** — Move cursor between rows in the file tree
- **j/k** — Move cursor between rows in the file tree (vim-style)
- **→** on a collapsed directory — Expand it
- **→** on a file — No action
- **←** on an expanded directory — Collapse it; cursor stays on the directory; preview clears or shows nothing (dirs have no content)
- **←** on a file or collapsed directory — Collapse the parent folder, cursor moves to parent; preview clears (now on a directory)
- **←** on a file at root level (no parent to collapse) — No action; preview stays on current file
- **←** on a collapsed directory at root level — No action; preview unchanged
- After expand/collapse, the cursor remains on the same directory row (never jumps)

### Edge cases for ← (collapse/navigate-to-parent)

| Current selection                          | Action                        | Cursor after            | Preview after                     |
| ------------------------------------------ | ----------------------------- | ----------------------- | --------------------------------- |
| Expanded directory                         | Collapse it                   | Stays on that directory | Clears (directory has no preview) |
| File inside `src/`                         | Collapse `src/`               | Moves to `src/` row     | Clears (now on directory)         |
| Collapsed directory inside `src/`          | Collapse `src/`               | Moves to `src/` row     | Clears                            |
| File at root level (no parent dir in tree) | Nothing                       | Unchanged               | Unchanged                         |
| Root-level directory (already collapsed)   | Nothing                       | Unchanged               | Unchanged                         |
| File while in flat view mode               | No action (no tree hierarchy) | Unchanged               | Unchanged                         |

**Preview pane rule:** When cursor lands on a directory (after ← collapses parent), the preview pane shows nothing meaningful — directories don't have file content. Current behavior: preview simply doesn't update (the `NodeHighlighted` message carries `entry=None` for directory nodes, which is filtered out before rendering).

- **Space** on a directory — Toggle expand/collapse
- **Tab** — Switch focus between the file tree and preview pane

## View Modes

- **v** — Cycle through: tree → flat name → flat path
- **Tree** — Hierarchical with expand/collapse, dirs with ▶/▼ twisties
- **Flat name** — Leaf filenames only, no paths, no hierarchy
- **Flat path** — Relative paths (e.g., `src / worker / foo.py`)
- Spaced paths (`/` → ` / `) is the default; toggled via command palette
- When sorting is activated, tree mode auto-switches to flat path (sorting requires a flat list)
- When sort is removed, the view restores to tree mode if that's where it was

## Column Sorting

- Click any column header — Cycle: ascending (▲) → descending (▼) → no sort
- Sorting only applies in flat view modes
- Sort indicators shown as suffix on the column header text

## Filtering

- **g** — Toggle git filter (shows all files that would appear in `git status`: modified, added, deleted, untracked, staged)
- **ctrl+f** — Focus the search input
- Search input provides fzf-like fuzzy filename matching (RapidFuzz)
- Filters compose: git filter applied first, then fuzzy search
- Filter state (git toggle + search query) persisted between sessions
- Collapsed folder state is preserved when toggling between filtered and unfiltered views

## Follow Mode

- **f** — Toggle follow mode on/off (notification shown)
- When ON and the file watcher detects a change:
  - The tree cursor automatically jumps to the last changed file
  - Parent folders are expanded to reveal it
  - The preview pane renders the file and scrolls to the first diff hunk
- When OFF, file watcher changes preserve the current cursor position
- Follow mode does not persist between sessions (always starts OFF)

## Preview Pane

- Automatically shows the highlighted file's content
- **d** — Cycle diff mode forward (configurable in preferences)
- **D** (shift) — Cycle diff mode backward
- **j**/**k** — Scroll up/down one line (when preview is focused via tab)
- **↑**/**↓** — Scroll up/down one line (when preview is focused)
- **space** — Page down with smooth scrolling (when preview is focused)
- **pageup**/**pagedown** — Page scroll with smooth animation
- **J**/**n** — Jump to next diff hunk not currently visible
- **K**/**N** — Jump to previous diff hunk not currently visible
- **e** — Open file in `$VISUAL`/`$EDITOR` (vim/nvim get `+line` for scroll position)
- **O** — Open file in default app via macOS `open` command (no-op on other platforms)
- Hunk jumps show 3 lines of context above the target; no-op if no changes
- Contiguous changed lines are treated as a single hunk for navigation

### Diff Modes

- **Full diff** — Syntax-highlighted full file with `+`/`-` markers and colored backgrounds (green `#002200` for added, red `#300000` for removed). Removed lines shown as a block before the first added line.
- **Gutter** — Syntax-highlighted file with a change column after line numbers: orange `●` for changed lines, green `+` for added, red `_` where deletions follow. When file has no changes, renders as plain file (no gutter column, no overview bar).
- **Unified diff** — Standard coloured unified diff output
- Configurable: `[preview] diff_modes` in preferences controls which modes `d` cycles through

### Scroll Position

- When switching diff modes, scroll position is preserved by source line number
- Scroll position is saved before entering unified diff mode and restored when leaving (unified diff only shows changes, so its scroll position can't represent the user's full-file position)
- Preview doesn't change when new files appear in the tree (stable during file watcher updates)
- When the previewed file changes on disk, scroll position is preserved
- In-progress page scroll animations are snapped before reading scroll position
- The 10-second timestamp refresh does not reset preview scroll

### Large File Handling

- Files > 50KB: loading indicator shown, rendering via background worker (cancellable by selecting another file)
- Files > 100KB: syntax highlighting disabled for speed (line numbers and diff markers still work)
- Files > 10MB: shown as centered message dialog ("File Too Large")
- Binary files (null byte in first 8KB): shown as centered message dialog ("Binary File")
- Message dialogs use a bordered Textual widget centered in the preview area

### Copy to Clipboard

- **Double-click** a line → copies `path:line` to clipboard, flashes highlight
- **Drag** across lines → live highlight (throttled to ~33fps), copies `path:start-end` on release
- Uses OSC 52 terminal clipboard (requires terminal setting enabled in iTerm2)
- Invalid lines in unified diff (headers, removed) are not selectable

## Columns

- **1–7** — Toggle individual columns
- **b** — Toggle blame columns (author + git time) and trigger background load
- Available columns: Name, Status (St), Lines (+/-), Size, Lines, Modified, Author, Git Time
- Size and Modified and Git Time columns use a 256-color gradient by relative magnitude
- Gradient toggled via command palette
- Blame columns show "..." while loading, then populate progressively
- Lines column shows line count for text files, or file size in grey for binary/empty files

## Gradient Colors

- Applied to Size, Modified, and Git Time columns
- Color ramp: `[15, 51, 45, 39, 33, 27, 57, 93, 129, 165, 201, 200, 199, 198, 197, 196]`
- White/cyan (low) → blue/purple (mid) → magenta/red (high)
- Ranges computed per the currently visible/filtered file set

## File Icons

- Loaded from `~/.config/lsd/icons.yaml` if present
- Resolution order: exact filename → file extension → filetype fallback (file/dir)
- Single-width icons (Nerd Font glyphs) padded with a space for alignment with double-width icons
- No PyYAML dependency required (custom parser)

## Git Integration

- Graceful degradation for non-git directories: hides status/lines columns
- `.gitignore` rules enforced via Dulwich's `IgnoreFilterManager` (handles nesting, negation, `**` globs)
- Git status: M (modified), A (added), D (deleted), ? (untracked), SM/SA/SD (staged variants)
- Deleted files shown with strikethrough, dimmed red filename (only on filename text, not indent/icon)
- `g` filter shows all files that would appear in `git status` (modified, added, deleted, untracked, staged)
- Diff computed against HEAD
- Diff parser uses block-based grouping: removed lines appear as a single block before the first added line that follows them

## Live File Watching

- File tree updates automatically when files change on disk
- Watchdog for native filesystem events; polling fallback if watchdog fails
- On change: rebuild file index, re-apply filters, sync table, restore cursor to previously selected file
- Column headers preserved during data refreshes (no flicker)
- Parent folders of changed files are auto-expanded to ensure visibility
- Preview updates in-place (no scroll reset) when the selected file's content changes
- Tree always rebuilds from latest entries on expand/collapse (new files in collapsed dirs appear on expand)
- Relative timestamps refresh every 10 seconds via `update_cell()` (no table rebuild)
- `.gamrstate` excluded from watching (prevents feedback loop)

## State Persistence

- Saved to `$XDG_STATE_HOME/gamr/<hash>.json` on quit (defaults to `~/.local/state/gamr/`)
- Legacy fallback: reads from `~/.config/gamr/state/` and local `.gamrstate` if present
- Restored on next launch if target directory matches
- Persisted state: view mode, diff mode, column toggles, spaced paths, gradient, overview style, collapsed directories, split position, selected file, git filter, search query

## Preferences

- Loaded from `$XDG_CONFIG_HOME/gamr/preferences.toml` on launch (defaults to `~/.config/gamr/`)
- Not modified by the app — user-edited only
- Available settings:
  - `[preview] diff_modes` — list of diff modes to cycle through with `d` (options: `"full"`, `"gutter"`, `"unified"`, default: all three)
  - `[preview] overview_styles` — list of overview styles to cycle through with `o` (options: `"line"`, `"quadrant"`, `"sextant"`, `"braille"`, `"off"`, default: all five)

## Resizable Split

- Draggable 1-character divider between tree and preview panes
- Divider is subtle (`$surface-lighten-1`, one shade lighter on hover)
- Split fraction persisted between sessions
- Uses `fr` units for pane sizing to avoid rounding gaps

## Diff Overview Bar

- 1-column bar docked to the right of the preview pane
- Visible in full diff and gutter modes (when changes exist); hidden in unified diff and plain preview
- **`o`** — Cycle overview style: line → quadrant → sextant → braille → off
- Five styles (all render on right side of cell for visual consistency):
  - **Line** (default): `▐` or space, 1 line per row
  - **Quadrant**: `▝`/`▗`/`▐`, 2 lines per row
  - **Sextant**: right-column sextant characters, 3 lines per row (requires Unicode 13.0 terminal)
  - **Braille**: right-column braille dots, 4 lines per row
  - **Off**: overview bar hidden

### Rendering Algorithm

- Bitmap-based: each changed line maps to slot(s) in the overview; contiguous changed lines produce contiguous filled slots (no gaps)
- Colors match the preview: green where added lines display, red where removed lines display; orange only when both map to the same character cell
- In full diff mode: overview maps by display row (includes removed-line rows) so colors align with the actual preview content
- In gutter mode: overview maps by source line (1:1 with preview)

### Scaling Behavior

- When file fits in view (lines ≤ height): 1:1 mapping, each changed line aligns with its corresponding preview line
- When file exceeds view: proportional scaling fills full bar height, never missing a change
- Overview style and state persisted between sessions
- **Terminal compatibility**: Sextant mode uses Unicode 13.0 "Symbols for Legacy Computing" characters. Supported in Ghostty, Kitty, and WezTerm. May render as boxes in macOS Terminal.app or older terminals. Configure available styles in preferences.

## Command Palette (ctrl+p)

- Toggle spaced paths
- Toggle gradient colors
- Cycle diff overview style (line/quadrant/sextant/braille/off)
