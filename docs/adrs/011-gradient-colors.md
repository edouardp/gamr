---
status: accepted
date: 2026-06-08
deciders: edouard
---

# ADR-011: Gradient Colors for Magnitude Columns

## Context and Problem Statement

How do we help users quickly identify outliers (largest files, most recently modified) in a long file list?

## Decision Outcome

Apply a 256-color gradient to the Size and Modified columns. Values are mapped linearly from min to max across visible entries onto a 16-step color ramp:

```
[15, 51, 45, 39, 33, 27, 57, 93, 129, 165, 201, 200, 199, 198, 197, 196]
```

This progresses from white → cyan → blue → purple → magenta → red, making small/old values cool-colored and large/recent values hot-colored.

### Toggle

Gradient is on by default. Toggled via command palette (`ctrl+p` → "gradient").

### Consequences

- Good, because outliers are instantly visible without reading numbers
- Good, because the gradient adapts to the current filtered set (recalculates min/max)
- Neutral, requires 256-color terminal support (degrades gracefully on 16-color)
