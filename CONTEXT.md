# Stock Watcher — Domain Glossary

> This glossary defines the ubiquitous language for the Stock Watcher project.
> It is implementation-free: no code structure, no technology choices.

---

## Core concepts

### Stock Quote (行情快照)

A point-in-time snapshot of a stock's trading data: current price, today's change,
open/high/low, volume, and turnover. A Quote is **immutable** once fetched — it
represents what the API returned at a specific moment, not a live stream.

### Market (市场)

An exchange where stocks are traded. Three markets are supported:

- **Shanghai (A-share, sh)** — Shanghai Stock Exchange, mainland China.
  Trading hours: 09:30–11:30, 13:00–15:00 (Beijing time, UTC+8), Mon–Fri.
- **Shenzhen (A-share, sz)** — Shenzhen Stock Exchange, mainland China.
  Same trading hours as Shanghai.
- **Hong Kong (HK, hk)** — Hong Kong Stock Exchange.
  Trading hours: 09:30–12:00, 13:00–16:10 (Beijing time, UTC+8), Mon–Fri.
  Includes the Closing Auction Session (16:00–16:10).

### Trading Calendar (交易日历)

Determines whether a given stock is currently in a trading session.
Calendar decisions are per-market and per-instant — there is no "trading day"
entity, only point-in-time queries.

### Watchlist (自选股)

The user's curated list of stock codes to monitor. Each entry is a
`{market_prefix}{raw_code}` string (e.g. `sh600519`). The watchlist is persisted
in `config.yaml` and can be modified from both the TUI and the config file.

### Alert (告警)

A rule that fires when a stock's price or change% crosses a threshold. Alerts are
**edge-triggered**: they fire exactly once when the condition becomes true, then
re-arm when the condition becomes false again. Four alert types:

- **Price Above** — price rises to or above a threshold
- **Price Below** — price falls to or below a threshold
- **Pct Above** — change% rises to or above a threshold
- **Pct Below** — change% falls to or below a negative threshold

### Alert History (告警历史)

A persistent log of alert firings. Each entry records: the stock code, alert type,
threshold value, the price at firing time, and the timestamp. History survives
application restarts.

---

## New concepts (TUI v2)

### Position (持仓)

A user's holding in a stock: **cost price** (买入均价) and **quantity** (持仓数量,
in shares). From these, the system computes:

- **Market Value** (市值) = `price × quantity`
- **Unrealized P&L** (浮动盈亏) = `(price - cost) × quantity`
- **P&L Percentage** (盈亏比) = `(price - cost) / cost × 100%`

A Position is associated with a watchlist entry. Not every watchlist stock needs
a position — positions are optional.

### Order Book (盘口)

The current bid/ask queue for a stock, showing the top 5 bid prices+volumes and
top 5 ask prices+volumes. Shown in the detail panel only (not in the main table).

### Detail Panel (详情面板)

A popup or side panel that shows extended information for a single stock:
order book, PE ratio, market cap, 52-week range, and recent alert history for
that stock.

### Column Set (列集)

The user can configure which columns appear in the main data table. Available
columns include the base set (code, name, price, change%, change amount, high,
low) plus optional columns (volume, turnover, open, PE, market cap).

---

## Data flow

```
Sina/Tencent API ──fetch──→ StockQuote ──update──→ DataTable row
                                      ──check───→ AlertRule ──fire──→ AlertHistory
                                      ──compute─→ Position P&L
```

- **Polling**: every N seconds (configurable), the app round-robins through the
  watchlist, fetching one quote per tick.
- **Hot-reload**: changes to `config.yaml` are detected automatically; the
  running app diffs the new config against current state and applies deltas
  without restart.
