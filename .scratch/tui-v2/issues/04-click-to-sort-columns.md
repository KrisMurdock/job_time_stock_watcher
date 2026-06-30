# 04 — Click-to-sort columns + raw value storage

Status: 📋 todo  
Labels: feature, phase-1

## Problem

`StockTable.update_quote()` stores cell values as Rich markup strings
(`"[bold #ff4444]+1.25%[/]"`). Calling `DataTable.sort()` on these strings
produces garbage alphabetical order. Need to store raw sortable values
separately and implement click-header-to-sort.

## Solution

### Raw value storage

Maintain a parallel dict in `StockTable`:
```python
self._raw: dict[str, dict[str, Any]] = {}  # row_key → {col_key: raw_value}
```

`update_quote()` stores both the markup cell and the raw value. Raw values:
- 方向 → `quote.change_pct or 0.0`
- 代码 → `quote.code`
- 名称 → `quote.name`
- 现价 → `quote.price or 0.0`
- 涨跌幅 → `quote.change_pct or 0.0`
- 涨跌额 → `quote.change_amount or 0.0`
- 最高 → `quote.high or 0.0`
- 最低 → `quote.low or 0.0`

### Click-to-sort behavior

Handle `DataTable.HeaderSelected`:
- Same column clicked: toggle ascending → descending → unsort
- Different column: ascending on new column
- Sorted column header gets ` ▲` or ` ▼` suffix

After sort: re-sort on every `update_quote()` if sort is active.

### Sort state

```python
self._sort_col: str | None = None
self._sort_reverse: bool = False
```

## Done when

- [ ] `StockTable` stores raw values alongside markup
- [ ] Click column header → sorts by that column
- [ ] Click again → reverse order
- [ ] Click third time → unsort (back to watchlist order)
- [ ] Sort indicator (▲/▼) on header
- [ ] New quotes maintain sort order
- [ ] Tests: sort by price, sort by change%, verify order correct
