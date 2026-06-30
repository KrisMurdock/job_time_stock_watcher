# PRD: Stock Watcher TUI v2

## Summary

A comprehensive upgrade of the Stock Watcher TUI: fix critical bugs, add
position tracking, richer market data, alert management, click-to-sort, detail
panel, settings UI, and quality-of-life improvements.

---

## Phase 0 — Bug fixes (必做，阻塞后续功能)

### 0.1 Fix stock search (P0)

**Problem:** `_parse_suggest_response()` field order is `name,market,code` but
code parses as `code,name,market`. All search results silently discarded.
HK market type `31` missing from URL and mapping.

**Fix:**
- Swap field indices in `_parse_suggest_response()`: parts[0]=name, parts[1]=market_type, parts[2]=raw_code
- Add `"31": "hk"` to `_sina_market_to_prefix()`, remove `"13"` (dead entry)
- Add `31` to suggest URL type list

### 0.2 Fix Ctrl+N hot-reload trigger (P1)

**Problem:** `config.yaml` line 4 documents "按 Ctrl+N 即可热加载" but no binding exists.

**Fix:** Add `Binding("ctrl+n", "reload_config", "热加载")` and an `action_reload_config`
handler that forces re-read of config.yaml.

---

## Phase 1 — Foundation: data model + sorting

### 1.1 Extend StockQuote model

Add fields available from API but currently discarded:

| Field | A-share (Sina) | HK (Tencent) | Type |
|-------|:---:|:---:|------|
| `open` | field[1] | field[5] | `float \| None` |
| `volume` | field[8] | field[6] | `float \| None` |
| `turnover` | field[9] | field[37] | `float \| None` |
| `pe` | — | field[39] | `float \| None` |
| `market_cap` | — | field[44] | `float \| None` |
| `bid` | field[6] | — | `float \| None` |
| `ask` | field[7] | — | `float \| None` |
| `bid_volumes` | fields[10,12,14,16,18] | — | `list[float]` |
| `ask_volumes` | fields[20,22,24,26,28] | — | `list[float]` |

Backward compatible — all new fields optional (`None` when unavailable).

### 1.2 Parse additional fields from both APIs

- Sina `parse_sina_response`: extract open (field[1]), volume (field[8]), turnover (field[9]),
  bid/ask + 5-level order book (fields[6,7,10–29])
- Tencent `parse_tencent_response`: extract open (field[5]), volume (field[6]),
  turnover (field[37]), PE (field[39]), market_cap (field[44])

### 1.3 Raw value storage for sortable columns

**Problem:** StockTable cells store Rich markup strings (`"[bold #ff4444]+1.25%[/]"`),
making `DataTable.sort()` sort alphabetically (garbage order).

**Solution:** Maintain a parallel `dict[str, dict[str, Any]]` (row_key → {column_key: raw_value})
in StockTable. On `HeaderSelected`:
1. Look up raw values for that column
2. Call `self.sort(column_key, key=lambda row: raw_values[row][col], reverse=...)`
3. Re-apply sort after every `update_quote()` if a sort is active

### 1.4 Click-to-sort on column headers

- Handle `DataTable.HeaderSelected` in `StockWatcherApp`
- Click once: ascending; click again: descending; click third: unsort (watchlist order)
- Visual indicator: append ` ▲` / ` ▼` to sorted column header label

---

## Phase 2 — Alert management

### 2.1 Alert indicator on table rows

- Add a `🔔` prefix (or leftmost column) to stock codes that have active alerts
- Visual only, no interaction change

### 2.2 Alert list popup

- Key: `v` (view) — shows a modal with all current alert rules
- Each row: code, name, type, threshold, status (armed / triggered)
- Actions: `d` to delete selected alert, `escape` to close
- Single alert delete preserves config.yaml comments (same `_save_yaml_list` path)

### 2.3 Alert history log (persistent)

- On alert fire: append to `alert_history.jsonl` (one JSON object per line)
- Fields: `timestamp`, `code`, `name`, `alert_type`, `threshold`, `price`, `change_pct`
- Key: `h` (history) — opens a scrollable view of recent alerts (last 200)
- Rotate log when > 10,000 entries (keep most recent 5,000)

---

## Phase 3 — Position tracking

### 3.1 Position model

```yaml
# config.yaml — new top-level key
positions:
  sh600519:
    cost: 1680.00
    quantity: 100
  hk00700:
    cost: 420.00
    quantity: 200
```

- `cost`: average buy price (买入均价), float, > 0
- `quantity`: shares held, int, > 0
- Positions loaded from config on startup, persisted on change

### 3.2 P&L computation

For each stock with a position:
- `market_value = price × quantity`
- `pnl = (price - cost) × quantity`
- `pnl_pct = (price - cost) / cost × 100%`

Computed on every quote update; constants when no new quote.

### 3.3 Position columns in main table

Add behind existing columns:
- `持仓量` — quantity (integer)
- `成本价` — cost price (2 decimals)
- `市值` — market value (2 decimals)
- `盈亏` — P&L amount (2 decimals, red/green)
- `盈亏比` — P&L% (2 decimals, red/green)

### 3.4 Position input UI

- Key: `p` (position) on highlighted row → modal dialog
- Input format: `成本 数量` (e.g. `1680 100`)
- Validates: cost > 0, quantity > 0, quantity integer
- Overwrites existing position; empty input → delete position
- Persists to config.yaml immediately

---

## Phase 4 — Extended data columns

### 4.1 New columns in main table

| Column | Key | Format | Market |
|--------|-----|--------|:---:|
| 今开 | `open` | `8.2f` | A + HK |
| 成交量 | `volume` | `12.0f` (shares) | A + HK |
| 成交额 | `turnover` | `10.2f` (yuan/HKD) | A + HK |
| 市盈率 | `pe` | `6.2f` | HK only |
| 总市值 | `market_cap` | `8.2f` (亿) | HK only |

### 4.2 Column visibility

- Default: show all A-share columns, hide PE/market_cap for HK-only stocks
- In `config.yaml`: `table_columns: [code, name, price, change_pct, ...]` allows user to
  reorder and hide columns
- Hot-reload picks up column changes

### 4.3 Detail panel — order book + extended info

- Key: `enter` on highlighted row → detail modal (side panel or overlay)
- Shows for the selected stock:
  - Full name, code, market
  - Current price (large), change% (colored)
  - Open / High / Low / Volume / Turnover
  - 5-level bid/ask order book (A-share only, Sina API)
  - PE / Market cap / 52-week range (HK only, Tencent API)
  - Recent alert history for this stock (last 10 entries)
- Auto-refreshes on each new quote for that stock
- `escape` to close

---

## Phase 5 — Settings panel

### 5.1 TUI settings dialog

- Key: `s` (settings) — modal overlay with editable fields:

| Setting | Type | Default |
|---------|------|---------|
| 轮询间隔(秒) | float | 2.5 |
| 请求超时(秒) | float | 10.0 |
| 退避基数(秒) | float | 5.0 |
| 退避上限(秒) | float | 120.0 |
| 退避乘数 | float | 2.0 |
| 告警音效命令 | str | "" |

- On save: writes to `config.yaml`, triggers hot-reload
- Reuses existing `_save_yaml_list` approach for comments preservation

---

## Phase 6 — Polish & QoL

### 6.1 Ctrl+N hot-reload (see 0.2)

### 6.2 Export CSV

- Key: `e` — exports current table data to `export_YYYYMMDD_HHMMSS.csv`
- Includes all visible columns
- Notification shows file path

### 6.3 Multi-market visual separation

- HK stocks: subtle background tint (`#1a1a2e` or similar dark blue)
- OR: add a `市场` column with `A股`/`港股` tag
- User preference via config: `hk_row_highlight: true`

### 6.4 Table scroll position preservation

- After sort, try to keep the previously highlighted row visible
- If the row was removed/moved, scroll to top

---

## Dependency graph

```
Phase 0 (Bug fixes)
  ↓
Phase 1 (Model extension + sort)
  ↓
┌─────────┬─────────┬─────────┐
↓         ↓         ↓         ↓
Phase 2   Phase 3   Phase 4   Phase 5
(Alerts)  (Position)(Columns) (Settings)
  ↓         ↓         ↓         ↓
  └─────────┴────┬────┴─────────┘
                 ↓
            Phase 6 (Polish)
```

Phases 2–5 can proceed in parallel after Phase 1.

---

## Out of scope (for v2)

- Webhook/外发通知 (defer to v3 — needs separate design for multi-provider)
- 实时分时图/Sparkline (needs canvas/graphical rendering, not feasible in Textual DataTable)
- 多账户/组合管理
- 条件单/止损止盈自动交易
- 历史K线数据缓存
