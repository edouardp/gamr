# Changelog

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
