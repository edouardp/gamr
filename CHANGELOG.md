# Changelog

## 0.4.0 (2026-06-23)

  - Kitty graphics protocol logo on supported terminals (Ghostty, Kitty, WezTerm)
  - Logo hidden during search, modals, and restored after editor exit
  - Logo preferences in `~/.config/gamr/preferences.toml` (`[logo]` section)
  - Set terminal title to "gamr" on launch, restore on exit
  - Restore terminal title after returning from $EDITOR
  - Focused pane header highlighted in purple (configurable via `[ui] focus_color`)
  - Preview pane header shows file icon and relative path
  - Preview pane focuses on click anywhere in the pane
  - Remove diff mode from preview pane header (shown in toolbar only)
  - Fix: initial diff mode now respects saved state on startup
  - Fix: status bar items auto-width to prevent text wrapping
  - Progressive async startup with native LoadingIndicator
  - Extract PreviewController from app.py
  - Follow mode: track known hunks, scroll to last hunk, skip if visible
  - Don't follow to new files when side-by-side is open; live-update modal
  - Static marketing website at gamr.edouard.nz
  - Website: mp4 demo videos for all features, interactive feature explorer
  - Website: docs page rewritten as user guide with keycap styling
  - CloudFormation infrastructure for S3/CloudFront/Route53 deployment
  - Makefile with deploy-infra, deploy-website, release, test targets
  - Interactive release chooser via TUI


## 0.3.0 (2026-06-20)

  - Git worktree support: correct working tree root detection for linked worktrees and bare-repo layouts
  - Watch shared commondir (packed-refs, refs/) for branch/tag changes in worktrees
  - Fix: DiffOverview visibility when toggling between message and content views
  - Fix: expand collapsed ancestors in follow mode before selecting file
  - Share DiffOverview widget between preview pane and side-by-side diff
  - Show deletion marker on preceding line for changed hunks with net removals
  - Cross-platform "Open in default app" (`O`): macOS/Linux/BSD/Windows/WSL2
  - Updated ADRs 007, 015, 017, 022 to reflect current implementation
  - Added AGENTS.md with repo rules for AI agents

## 0.2.5 (2026-06-14)

  - Fix: cycling diff mode (`d`) no longer resets overview style indicator to "off"
  - Fix: leaving git filter preserves cursor on the previously previewed file
  - Fix: typo "assisstant" → "assistant" in logo tagline
  - Terminal-aware logo: sextant version for Ghostty/Kitty/WezTerm/cmux, box-drawing fallback for others
  - Fallback logo uses `future` figlet font style (box-drawing chars, works everywhere)

## 0.2.4 (2026-06-14)

  - Terminal-aware logo: sextant version for Ghostty/Kitty/WezTerm/cmux, box-drawing fallback for others
  - Detects `TERM`/`TERM_PROGRAM` for sextant support (ghostty, kitty, wezterm, cmux)
  - Fallback logo uses `future` figlet font (box-drawing chars supported everywhere)
  - Logo includes taglines: "Git-aware / Agentic coding assistant / Monitor & Review tool"
  - R letter refined with smoother diagonal stroke

## 0.2.3 (2026-06-14)

  - Rounded logo using Unicode diagonal block elements (🭆🭑🭧🭜)
  - Wider M in logo using diagonal smooth mosaic characters
  - Toolbar status bar: clickable indicators for view, git filter, follow, diff, overview, blame
  - Status shows "sorted" when column sort active, updates on header click
  - `J`/`n` and `K`/`N` hunk jumping now works from any focus (promoted to app-level)
  - `V` cycles view mode in reverse
  - `?` keyboard shortcuts help popup
  - Persist preview scroll position between sessions

## 0.2.2 (2026-06-14)

  - Toolbar status indicators: view mode, file count, git filter, follow, diff mode, overview style, blame
  - Clickable status items — click to cycle/toggle the corresponding setting
  - `?` keyboard shortcuts help popup (auto-sized to content)
  - `V` cycles view mode in reverse
  - Persist preview scroll position between sessions
  - Status indicators: left side for file pane, right side for preview pane (right-justified)

## 0.2.1 (2026-06-14)

  - Fix double-width unicode (emoji, CJK) misaligning the side-by-side divider
  - Add `J`/`n` and `K`/`N` hunk jumping in side-by-side modal (matches preview pane)
  - `j`/`k` scroll in side-by-side now handled directly (fixes unresponsive keys)

## 0.2.0 (2026-06-14)

  - Side-by-side diff modal (`s`): full old/new file view with aligned padding
  - Syntax highlighting in side-by-side (Monokai theme, both panels)
  - Character-level inline diff highlighting (brighter background on changed chars)
  - Three-color scheme: orange (changed), green (added), red (removed), grey (padding gaps)
  - Diff overview bar in side-by-side modal
  - Live refresh: side-by-side updates when file changes on disk
  - Scroll position syncs between preview pane and side-by-side modal (both directions)
  - Native scroll handling in modal (keyboard, mouse wheel, scrollbar drag)
  - `gamr.sh` launcher: renamed GAMR_DIR to TARGET_DIR, accepts optional directory argument
  - ADR-029: side-by-side diff modal

## 0.1.13 (2026-06-12)

  - Cross-platform fixes for Windows, BSD, and Linux
  - Git paths use forward slashes consistently (fixes Dulwich on Windows)
  - Gitignore filter uses POSIX paths (fixes ignore rules on Windows)
  - Flat path display uses forward slashes on all platforms
  - State file path comparison uses Path.resolve() (handles Windows drive letter casing)
  - Line counting uses explicit UTF-8 encoding (avoids Windows locale issues)
  - File watcher always polls alongside native backend (fixes silent event loss on BSD/Linux)

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
