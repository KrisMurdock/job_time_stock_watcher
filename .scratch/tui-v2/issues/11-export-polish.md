# 11 — Export CSV + multi-market visual separation + polish

Status: 📋 todo  
Labels: feature, polish, phase-6

## 11a. Export CSV

- Key `e` → export current table to `export_YYYYMMDD_HHMMSS.csv`
- Includes all visible columns (columns currently shown, not hidden ones)
- Values are raw (not Rich markup)
- UTF-8 BOM for Excel compatibility on Windows
- Notification shows file path after export

## 11b. Multi-market visual separation

- HK stocks: subtle row background tint (`rgba(30, 30, 50, 0.3)` or `#1a1a2e`)
- Config toggle: `hk_row_highlight: true` (default `true`)
- OR: add a narrow `市场` column with `A股`/`港股` tag (2 chars wide)

## 11c. Scroll position preservation

- After sort operation, keep the previously highlighted row in view
- If highlighted row was removed, scroll to top
- `DataTable.move_cursor()` can be used to restore position

## Done when

- [ ] CSV export works with raw values, UTF-8 BOM
- [ ] Multi-market separation visible (row tint or tag column)
- [ ] Scroll position preserved after sort
