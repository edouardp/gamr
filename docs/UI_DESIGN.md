# UI Design Rules

## Navigation

- **↑/↓** — Move cursor between rows in the file tree
- **→** on a collapsed directory — Expand it
- **→** on a file — No action
- **←** on an expanded directory — Collapse it; cursor stays on the directory; preview clears or shows nothing (dirs have no content)
- **←** on a file or collapsed directory — Collapse the parent folder, cursor moves to parent; preview clears (now on a directory)
- **←** on a file at root level (no parent to collapse) — No action; preview stays on current file
- **←** on a collapsed directory at root level — No action; preview unchanged

### Edge cases for ← (collapse/navigate-to-parent)

| Current selection                          | Action                        | Cursor after            | Preview after                     |
| ------------------------------------------ | ----------------------------- | ----------------------- | --------------------------------- |
| Expanded directory                         | Collapse it                   | Stays on that directory | Clears (directory has no preview) |
| File inside `src/`                         | Collapse `src/`               | Moves to `src/` row     | Clears (now on directory)         |
| Collapsed directory inside `src/`          | Collapse `src/`               | Moves to `src/` row     | Clears                            |
| File at root level (no parent dir in tree) | Nothing                       | Unchanged               | Unchanged                         |
| Root-level directory (already collapsed)   | Nothing                       | Unchanged               | Unchanged                         |
| File while in flat view mode               | No action (no tree hierarchy) | Unchanged               | Unchanged                         |

**Preview pane rule:** When cursor lands on a directory (after ← collapses parent), the preview pane shows nothing meaningful — directories don't have file content. The preview should retain its last content but dim or show "Select a file to preview" if we want to be explicit. Current behavior: preview simply doesn't update (the `NodeHighlighted` message carries `entry=None` for directory nodes, which is filtered out before rendering).
- **Space** on a directory — Toggle expand/collapse
- **Tab** — Switch focus between the file tree and preview pane
- After expand/collapse, the cursor remains on the same directory row

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

- **g** — Toggle git modified filter (shows only modified files)
- **ctrl+f** — Focus the search input
- Search input provides fzf-like fuzzy filename matching (RapidFuzz)
- Filters compose: git modified filter applied first, then fuzzy search
- Filter state (modified toggle + search query) persisted between sessions
- Collapsed folder state is preserved when toggling between filtered and unfiltered views

## Follow Mode

- **f** — Toggle follow mode on/off (notification shown)
- When ON and the file watcher detects a change:
  - The tree cursor automatically jumps to the last changed file
  - Parent folders are expanded to reveal it
  - The preview pane renders the file
  - If the file is git-modified, the preview scrolls to the first diff hunk
- When OFF, file watcher changes preserve the current cursor position
- Follow mode does not persist between sessions (always starts OFF)

## Preview Pane

- Automatically shows the highlighted file's content
- **d** — Cycle diff mode forward: full diff → gutter → unified diff
- **D** (shift) — Cycle diff mode backward
- Diff modes only apply to files with git changes; clean files show gutter mode as plain file
- Full diff — Syntax-highlighted full file with `+`/`-` markers and colored backgrounds (green `#002200` for added, red `#300000` for removed)
- Gutter — Syntax-highlighted file with a change column after line numbers: orange `●` for changed lines, green `+` for added, red `_` where deletions follow. When file has no changes, renders as plain file (no gutter column, no overview bar).
- Unified diff — Standard coloured unified diff output
- Preview and full diff share identical rendering (same line numbers, same syntax highlighting)
- Monokai background (`#272822`) fills the entire pane
- Header bar (pinned, doesn't scroll) shows filename on left, diff mode on right
- When switching diff modes, scroll position is preserved by source line number mapping
- Preview doesn't change when new files appear in the tree (stable during file watcher updates)
- When the previewed file changes on disk, scroll position is preserved by source line mapping
- The 10-second timestamp refresh does not reset preview scroll
- **Double-click** a line → copies `path:line` to clipboard, flashes highlight
- **Drag** across lines → live highlight, copies `path:start-end` on release
- Invalid lines in unified diff (headers, removed) are not selectable

## Columns

- **1–6** — Toggle individual columns
- **b** — Toggle blame columns (author + git time) and trigger background load
- Available columns: Name, Status (St), Lines (+/-), Size, Modified, Author, Git Time
- Size and Modified columns use a 256-color gradient by relative magnitude
- Gradient toggled via command palette
- Blame columns show "..." while loading, then populate progressively

## Gradient Colors

- Applied to Size and Modified columns
- Color ramp: `[15, 51, 45, 39, 33, 27, 57, 93, 129, 165, 201, 200, 199, 198, 197, 196]`
- White/cyan (low) → blue/purple (mid) → magenta/red (high)
- Ranges computed per the currently visible/filtered file set

## File Icons

- Loaded from `~/.config/lsd/icons.yaml` if present
- Resolution order: exact filename → file extension → filetype fallback (file/dir)
- No PyYAML dependency required (custom parser)

## Git Integration

- Graceful degradation for non-git directories: hides status/lines columns
- `.gitignore` rules enforced via Dulwich's `IgnoreFilterManager` (handles nesting, negation, `**` globs)
- Git status: M (modified), A (added), D (deleted), ? (untracked), SM/SA/SD (staged variants)
- Diff computed against HEAD

## Live File Watching

- File tree updates automatically when files change on disk
- Watchdog for native filesystem events; polling fallback if watchdog fails
- On change: rebuild file index, re-apply filters, sync table incrementally (only changed rows update)
- Column headers preserved during data refreshes (no flicker)
- Parent folders of changed files are auto-expanded to ensure visibility
- Preview updates in-place (no scroll reset) when the selected file's content changes
- Relative timestamps refresh every 10 seconds via `update_cell()` (no table rebuild)
- `.gamrstate` excluded from watching (prevents feedback loop)

## State Persistence

- Saved to `~/.config/gamr/state.json` on quit
- Restored on next launch if target directory matches
- Persisted state: view mode, diff mode, column toggles, spaced paths, gradient, collapsed directories, split position, selected file, selected filter IDs, search query

## Resizable Split

- Draggable 1-character divider between tree and preview panes
- Divider is subtle (`$surface-lighten-1`, one shade lighter on hover)
- Split fraction persisted between sessions
- Uses `fr` units for pane sizing to avoid rounding gaps

## Diff Overview Bar

- 1-column bar docked to the right of the preview pane
- Only visible in full diff mode; hidden in unified diff and plain preview
- Shows file-level change distribution: green (added), red (removed), yellow (mixed), dim (unchanged)
- Two styles toggled via command palette (`ctrl+p` → "braille"):
  - **Line mode** (default): `┃`/`│` characters
  - **Braille mode**: Unicode braille dots packing 4 source lines per terminal row

## Command Palette (ctrl+p)

- Toggle spaced paths
- Toggle gradient colors
- Toggle diff overview style (line/braille)
