---
status: accepted
date: 2026-06-08
deciders: edouard
---

# ADR-012: lsd Icons Config Support

## Context and Problem Statement

How do we display meaningful file-type icons without bundling a large icon database or adding heavy dependencies?

## Decision Outcome

Load icons from `~/.config/lsd/icons.yaml` if present (the same config used by the `lsd` file lister). This file has three sections:

- `name:` — exact filename → icon (e.g., `Dockerfile: 🐋`)
- `extension:` — file extension → icon (e.g., `py: 🐍`)
- `filetype:` — fallback by type (e.g., `file: 📄`, `dir: 📂`)

### Parsing

Uses a simple line-by-line parser (no PyYAML dependency required). Falls back to `📄`/`📂` if config is absent.

### Consequences

- Good, because users who already use lsd get consistent icons
- Good, because no additional dependency (PyYAML optional, custom parser as fallback)
- Neutral, users without lsd config get generic file/folder icons
