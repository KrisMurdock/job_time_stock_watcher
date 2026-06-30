# 03 — Extend StockQuote model + parse additional API fields

Status: 📋 todo  
Labels: feature, phase-1

## Summary

Both Sina (A-share) and Tencent (HK) APIs return fields that are currently
discarded: open, volume, turnover, bid/ask, PE, market cap. Extend the
`StockQuote` model and parse these fields.

## New StockQuote fields

| Field | Type | A-share source | HK source |
|-------|------|:---:|:---:|
| `open` | `float \| None` | Sina field[1] | Tencent field[5] |
| `volume` | `float \| None` | Sina field[8] (shares) | Tencent field[6] |
| `turnover` | `float \| None` | Sina field[9] (yuan) | Tencent field[37] (HKD) |
| `bid` | `float \| None` | Sina field[6] | — |
| `ask` | `float \| None` | Sina field[7] | — |
| `bid_prices` | `list[float]` | Sina fields[11,13,15,17,19] | — |
| `bid_volumes` | `list[float]` | Sina fields[10,12,14,16,18] | — |
| `ask_prices` | `list[float]` | Sina fields[21,23,25,27,29] | — |
| `ask_volumes` | `list[float]` | Sina fields[20,22,24,26,28] | — |
| `pe` | `float \| None` | — | Tencent field[39] |
| `market_cap` | `float \| None` | — | Tencent field[44] (亿) |

All new fields default to `None`. Backward compatible.

## Done when

- [ ] `StockQuote` model updated with new fields
- [ ] `parse_sina_response()` extracts open, volume, turnover, bid/ask, 5-level order book
- [ ] `parse_tencent_response()` extracts open, volume, turnover, PE, market cap
- [ ] Existing tests pass (check `test_models.py`, `test_fetcher.py`)
- [ ] New test: verify field extraction from real API response strings
