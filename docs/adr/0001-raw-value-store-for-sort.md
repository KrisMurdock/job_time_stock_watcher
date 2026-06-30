# ADR 0001 — Raw-value store for DataTable sort

## Status

Proposed

## Context

Textual's `DataTable.sort()` sorts rows by their cell values (strings). Our
`StockTable.update_quote()` stores Rich markup strings in cells (e.g.
`"[bold #ff4444]+1.25%[/]"`) to get colored text. Sorting on these markup
strings produces garbage alphabetical order.

**Alternatives considered:**

### A. Strip markup before sort

Parse the Rich markup string to extract the numeric value. Fragile — depends
on markup format stability, and doesn't work for direction arrows.

### B. Store raw values, apply markup at render

Override `DataTable._render_cell()` to apply Rich markup dynamically from raw
values. Requires subclassing internals that may change across Textual versions.

### C. Parallel raw-value dict (chosen)

Maintain `self._raw: dict[row_key, dict[col_key, Any]]` alongside the DataTable
rows. On sort, provide a `key` callable that looks up raw values. Still requires
re-sorting after every `update_quote()` since `add_row` breaks sort order.

## Decision

Option C — parallel `_raw` dict.

## Rationale

- Minimal coupling to Textual internals (no `_render_cell` override)
- Works with any column type (float, string, enum)
- Easy to extend for new columns (just add raw value entry)
- The re-sort-after-update cost is negligible for our row count (< 100)

## Consequences

- `StockTable` has a new responsibility: maintaining `_raw` alongside DataTable rows
- `update_quote()` must be followed by `_reapply_sort()` when sort is active
- `remove_row()` / `clear()` must clean up `_raw` entries
- Column header labels are modified in-place (`col ▲`) to show sort state —
  slight coupling to Textual's `DataTable._column_labels` structure
