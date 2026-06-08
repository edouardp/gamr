# Git + Diff TUI

## Specification

A python based TUI that uses a live file watcher to always show an up to date list of files in a folder (and be git aware if the folder is a repo - stretch goals, intelligently handle git worktrees). Files can be filtered in various useful ways, including by only showing files with certain git statuses like modified, untracked etc.

Metadata about the file (lines changed, add, removed - size - modification age - etc) can be turned on and off in a "tree-table" pane. File structure can be a tree, but that tree is column 1 in a table with other metadata being in the other columns. 

Seperate there is a second pane that shows the contents of the file, or diffs in the case of diffable files in a git repo.