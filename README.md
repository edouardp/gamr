# Gamr

**G**it-aware **A**gent **M**onitor & **R**eview — a TUI for reviewing AI agent work with live watching, fuzzy search, and diff preview.

## Features

- **Live file watching** — tree updates automatically when files change (watchdog + polling fallback)
- **Git integration** — pure Python via Dulwich, no git binary required
  - File status indicators (Modified, Added, Deleted, Untracked, Staged)
  - Deleted files shown with strikethrough styling
  - Three diff modes: full file diff, gutter markers, unified diff (`d`/`D` to cycle)
  - Blame data (last author, last modified) loaded in background
  - Bulk blame via single log walk with tree diffing (fast on large repos)
  - Respects `.gitignore` rules
- **Three view modes** — tree, flat filenames, flat relative paths (`v` to cycle)
- **Column sorting** — click any column header to sort asc/desc/none
- **Fuzzy search** — fzf-like filename filtering with RapidFuzz
- **Git status filtering** — `g` to toggle showing only modified files
- **Syntax-highlighted preview** — Monokai theme, scrollable, line numbers
- **Copy file references** — double-click or drag lines to copy `path:line` to clipboard
- **Full file diff** — syntax highlighting with inline +/- markers and colored backgrounds
- **Side-by-side diff** — modal popup (`s`) showing old/new files aligned with syntax highlighting, character-level change highlighting, and live refresh
- **Diff overview bar** — 1-column change map with 4 density modes (`o` to cycle: line, quadrant, sextant, braille)
- **Gradient colors** — size, modification time, and git blame time columns colored by relative magnitude
- **File icons** — loads from `~/.config/lsd/icons.yaml` if present
- **Resizable split pane** — drag the divider between tree and preview
- **Desktop-style navigation** — ←/→ to collapse/expand folders, ← on file collapses parent
- **State persistence** — view mode, columns, collapsed dirs, selection, filters saved between sessions
- **Preferences file** — `~/.config/gamr/preferences.toml` for user defaults (e.g., diff mode cycle)
- **Graceful degradation** — works on non-git directories (hides git UI)
- **Keyboard shortcuts help** — `?` shows all keybindings in a popup
- **Toolbar status indicators** — clickable view mode, diff mode, overview, follow, blame, file count

## Install

Requires Python 3.11+.

```sh
uv sync
uv run gamr [path]
```

## Keybindings

| Key      | Action                                               |
| -------- | ---------------------------------------------------- |
| `↑`/`↓`  | Navigate files                                       |
| `j`/`k`  | Navigate files (tree) or scroll (preview)            |
| `→`      | Expand directory                                     |
| `←`      | Collapse directory (or parent if on file)            |
| `space`  | Toggle expand/collapse (tree) or page down (preview) |
| `v`      | Cycle view mode (tree → flat name → flat path)       |
| `V`      | Cycle view mode reverse                              |
| `d`      | Cycle diff mode (full → gutter → unified)            |
| `D`      | Cycle diff mode reverse                              |
| `s`      | Side-by-side diff popup                              |
| `J`/`n`  | Jump to next diff hunk (preview)                     |
| `K`/`N`  | Jump to previous diff hunk (preview)                 |
| `o`      | Cycle diff overview style                            |
| `g`      | Toggle git modified filter                           |
| `f`      | Toggle follow mode (auto-select last changed file)   |
| `ctrl+f` | Focus search input                                   |
| `b`      | Toggle blame columns (last author, git time)         |
| `1`–`7`  | Toggle individual columns                            |
| `O`      | Open file in default app                             |
| `tab`    | Switch focus between tree and preview                |
| `ctrl+p` | Command palette (spaced paths, gradient toggle)      |
| `?`      | Show keyboard shortcuts help                         |
| `q`      | Quit (saves state)                                   |

Column headers are clickable to sort (ascending → descending → none).

## Architecture

```
src/gamr/
├── app.py                  # Textual app, keybindings, orchestration
├── commands.py             # Command palette provider
├── models.py               # FileEntry, GitStatus, DiffMode, etc.
├── state.py                # Persistent state management
├── preferences.py          # User preferences (~/.config/gamr/preferences.toml)
├── gamr.tcss               # Stylesheet
├── services/
│   ├── diff_parser.py      # Unified diff parsing into DiffData
│   ├── file_scanner.py     # Watchdog + polling fallback + git state watcher
│   ├── file_index.py       # Merges scanner + git into FileEntry list
│   ├── git_provider.py     # GitProvider ABC + Dulwich implementation
│   ├── filter.py           # Fuzzy and status filtering
│   └── icons.py            # lsd icons.yaml loader
└── widgets/
    ├── file_tree_table.py  # DataTable with tree semantics
    ├── tree_data.py        # Tree building and sorting logic
    ├── toolbar.py          # Toolbar (logo + search input)
    ├── preview_pane.py     # Syntax highlighting + diff view
    ├── side_by_side.py     # Side-by-side diff modal
    ├── help.py             # Keyboard shortcuts help modal
    └── split.py            # Resizable horizontal split
```

## Dependencies

- [Textual](https://textual.textualize.io/) — TUI framework
- [Dulwich](https://dulwich.io/) — pure Python git (no compiled deps)
- [watchdog](https://github.com/gorakhargosh/watchdog) — filesystem events
- [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz) — fuzzy string matching

## Tests

```sh
uv run pytest
```

## Documentation

- [UI Design Rules](docs/UI_DESIGN.md) — all interaction behaviors and edge cases
- [Architecture Decision Records](docs/adrs/README.md) — 29 ADRs covering all design choices
