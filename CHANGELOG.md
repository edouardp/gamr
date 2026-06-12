# Changelog

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
