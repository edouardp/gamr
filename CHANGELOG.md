# Changelog

## 0.1.12 (2026-06-12)

  - New "Lines" column: shows line count for text files, file size (grey) for binary
  - Column toggle keys renumbered: 1=Status, 2=+/-, 3=Size, 4=Lines, 5=Modified, 6=Author, 7=Git Time
  - Bulk blame: single log walk with tree diffing (120x faster on large repos)
  - Blame cache persists across file index rebuilds; only changed files re-blamed
  - Blame worker starts on mount if columns are visible (was only on toggle)
  - Blame worker no longer cancelled by non-git file changes
  - Git Time column now uses gradient colors (separate range from Modified)
  - `O` opens file in default macOS app (no-op on other platforms)
  - Fixed scroll position jumping on file watcher updates and blame refreshes
  - Fixed toolbar not showing search input when restoring saved filter query
  - Enter in search input returns focus to tree (same as Escape)
  - Hidden blame toggle (`b`) from footer
  - ADR-028: bulk blame via tree diffing


## 0.1.11 (2026-06-12)

  - Toolbar with sextant logo (replaces plain search bar), swaps to search on `/`
  - Escape in search returns focus to file tree and restores logo
  - `/` replaces ctrl+f for search focus (vim-style)
  - Tighter fuzzy matching: queries with `.` or `/` use exact substring match; threshold raised to 70
  - `e` launches editor with `+set number +line +normal! zt` for vim/nvim
  - Deleted files show "ℹ️ File Deleted" message instead of error
  - Replaced tuple returns with `RenderResult` and `GutterMarkers` dataclasses
  - Fixed private method access across class boundaries
  - Renamed FilterBar → Toolbar throughout codebase

## 0.1.10 (2026-06-12)

  - Diff overview: bitmap-based rendering, contiguous changes always contiguous
  - Diff overview: 4 density modes + off (`o` to cycle), configurable in preferences
  - Diff overview: display-row coloring in full diff mode (matches preview colors)
  - Diff parser: block-based grouping (fixes repeated removed lines in full diff)
  - Git filter (`g`): now shows all files in `git status` (modified, added, deleted, untracked, staged)
  - Deleted files shown with strikethrough dim red filename
  - `e` opens `$VISUAL`/`$EDITOR` at current scroll position
  - Tree always rebuilds from entries on expand (no stale nodes)
  - Cursor preserved after file watcher rebuild
  - Overview styles and scaling configurable in preferences.toml
  - XDG_STATE_HOME for state, XDG_CONFIG_HOME for config (with legacy fallback)
  - Comprehensive UI_DESIGN.md rewrite

## 0.1.9 (2026-06-12)

  - Fixed PyPI package missing long description (README now included in build)

## 0.1.8 (2026-06-12)

  - Async preview rendering for files >50KB (loading indicator, cancellable)
  - Skip syntax highlighting for files >100KB, reject files >10MB
  - Centered dialog message for binary/large/unreadable files
  - Long filenames no longer crash the preview header
  - Respect `$XDG_CONFIG_HOME` and `$XDG_STATE_HOME` per XDG spec
  - State files moved to `$XDG_STATE_HOME/gamr/` (legacy path still read)
  - Single-width file icons padded for alignment
  - Fixed follow mode not scrolling to first change hunk
  - Refactored: deduplicated preview rendering, extracted helpers, cleaner SRP

## 0.1.7 (2026-06-12)

  - Added `~/.config/gamr/preferences.toml` for user defaults
  - `[preview] diff_modes` controls which modes `d` cycles through
  - Braille/line overview mode now persisted between sessions
  - Fixed braille diff overview not filling the bar for shorter files

## 0.1.6 (2026-06-12)

  - Smooth scrolling for page up/down/space in preview pane
  - Fixed scroll position lost when cycling through diff modes via unified diff
  - Fixed scroll position read during in-flight animation giving wrong results

## 0.1.5 (2026-06-11)

  - Added vim-style keybindings: `j`/`k` to navigate file tree and scroll preview
  - Arrow keys and page up/down now work in preview pane when focused via tab
  - `space` in preview pane scrolls down a page (with 4-line overlap)
  - `J`/`n` and `K`/`N` jump to next/prev diff hunk in full diff and gutter modes
  - Hunk navigation shows 3 lines of context above the target
  - Fixed tab not switching focus to preview pane
  - Reduced lag on drag-to-select line highlighting (throttled updates)

## 0.1.4 (2026-06-11)

  - Replaced filter buttons (M, A, D, ?, S) with single `g` keybinding for git modified filter
  - Fixed collapsed folders lost when toggling between filtered and unfiltered views
  - Added git worktree support plan (docs/GIT_WORKTREES.md)

## 0.1.3 (2026-06-10)

  - Fixed braille diff overview alignment for short files — dots now align 1:1 with source lines when content fits on screen
  - Fixed release script to run uv lock after version bump

## 0.1.2 (2026-06-10)

  - State files now stored in ~/.config/gamr/state/ instead of polluting project directories
  - Existing local .gamrstate files are still respected for backward compatibility
  - Removed unnecessary horizontal scrollbar from preview pane (content wraps with Textual 1.x)

## 0.1.1 (2025-06-10)

  Initial public release.

  - Live file watching with automatic tree updates (watchdog + polling fallback)
  - Pure Python git integration via Dulwich — no git binary required
  - File status indicators (Modified, Added, Deleted, Untracked, Staged)
  - Three diff modes: full file, gutter markers, unified diff
  - Three view modes: tree, flat filenames, flat relative paths
  - Fuzzy filename search with RapidFuzz
  - Git status filtering toggles
  - Syntax-highlighted preview with Monokai theme
  - Column sorting, resizable split pane, state persistence
  - Background blame loading (author + last modified)
  - .gitignore support
  - Graceful degradation on non-git directories
