# Changelog

0.1.1 (2025-06-10)

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
