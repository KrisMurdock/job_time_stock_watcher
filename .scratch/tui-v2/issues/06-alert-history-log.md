# 06 — Persistent alert history log

Status: 📋 todo  
Labels: feature, phase-2

## Summary

Log every alert firing to a persistent file (`alert_history.jsonl`). Provide
a viewer in the TUI.

## Details

- On alert fire (`_fire_alert`), append one JSON line to `alert_history.jsonl`:
  `{"ts": "2026-06-30T14:25:00+08:00", "code": "hk00700", "name": "腾讯控股", "type": "price_above", "threshold": 436.0, "price": 436.50, "change_pct": 1.25}`
- Rotate: when > 10,000 lines, keep last 5,000
- Key `h` → opens scrolling view (last 200 entries, newest first)
- Each row: `14:25  hk00700 腾讯控股  price_above 436.00 → 现价436.50 (+1.25%)`
- Read-only, `escape` to close

## Done when

- [ ] Alert fires append to `alert_history.jsonl`
- [ ] Rotation keeps file bounded at 10,000 lines
- [ ] `h` key opens history viewer
- [ ] Viewer shows last 200 entries, newest first
- [ ] Contains: time, code, type, threshold, price, change_pct
