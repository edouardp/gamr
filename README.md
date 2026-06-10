# Gamr

**G**it-aware **A**gent **M**onitor & **R**eview — a TUI for reviewing AI agent work with live watching, fuzzy search, and diff preview.

## Features

- **Live file watching** — tree updates automatically when files change (watchdog + polling fallback)
- **Git integration** — pure Python via Dulwich, no git binary required
  - File status indicators (Modified, Added, Deleted, Untracked, Staged)
  - Three diff modes: full file diff, gutter markers, unified diff (`d`/`D` to cycle)
  - Blame data (last author, last modified) loaded in background
  - Respects `.gitignore` rules
- **Three view modes** — tree, flat filenames, flat relative paths (`v` to cycle)
- **Column sorting** — click any column header to sort asc/desc/none
- **Fuzzy search** — fzf-like filename filtering with RapidFuzz
- **Git status filtering** — `g` to toggle showing only modified files
- **Syntax-highlighted preview** — Monokai theme, scrollable, line numbers
- **Copy file references** — double-click or drag lines to copy `path:line` to clipboard
- **Full file diff** — syntax highlighting with inline +/- markers and colored backgrounds
- **Diff overview bar** — 1-column change map (line or braille style) in full diff mode
- **Gradient colors** — size and modification time columns colored by relative magnitude
- **File icons** — loads from `~/.config/lsd/icons.yaml` if present
- **Resizable split pane** — drag the divider between tree and preview
- **Desktop-style navigation** — ←/→ to collapse/expand folders, ← on file collapses parent
- **State persistence** — view mode, columns, collapsed dirs, selection, filters saved between sessions
- **Graceful degradation** — works on non-git directories (hides git UI)

## Install

Requires Python 3.11+.

```sh
uv sync
uv run gamr [path]
```

## Keybindings

| Key      | Action                                             |
| -------- | -------------------------------------------------- |
| `↑`/`↓`  | Navigate files                                     |
| `→`      | Expand directory                                   |
| `←`      | Collapse directory (or parent if on file)          |
| `space`  | Toggle expand/collapse                             |
| `v`      | Cycle view mode (tree → flat name → flat path)     |
| `d`      | Cycle diff mode (full → gutter → unified)           |
| `D`      | Cycle diff mode reverse                            |
| `g`      | Toggle git modified filter                         |
| `f`      | Toggle follow mode (auto-select last changed file) |
| `ctrl+f` | Focus search input                                 |
| `b`      | Toggle blame columns (last author, git time)       |
| `1`–`6`  | Toggle individual columns                          |
| `tab`    | Switch focus between tree and preview              |
| `ctrl+p` | Command palette (spaced paths, gradient toggle)    |
| `q`      | Quit (saves state)                                 |

Column headers are clickable to sort (ascending → descending → none).

## Architecture

```
src/gamr/
├── app.py              # Textual app, keybindings, orchestration
├── commands.py         # Command palette provider
├── models.py           # FileEntry, GitStatus, DiffMode, etc.
├── state.py            # Persistent state management
├── gamr.tcss          # Stylesheet
├── services/
│   ├── diff_parser.py  # Unified diff parsing into DiffData
│   ├── file_scanner.py # Watchdog + polling fallback + git state watcher
│   ├── file_index.py   # Merges scanner + git into FileEntry list
│   ├── git_provider.py # GitProvider ABC + Dulwich implementation
│   ├── filter.py       # Fuzzy and status filtering
│   └── icons.py        # lsd icons.yaml loader
└── widgets/
    ├── file_tree_table.py  # DataTable with tree semantics
    ├── tree_data.py        # Tree building and sorting logic
    ├── filter_bar.py       # Search input + filter state
    ├── preview_pane.py     # Syntax highlighting + diff view
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
- [Architecture Decision Records](docs/adrs/README.md) — 23 ADRs covering all design choices
