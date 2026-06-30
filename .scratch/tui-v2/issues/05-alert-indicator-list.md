# 05 — Alert indicator + alert list popup

Status: 📋 todo  
Labels: feature, phase-2

## Summary

Add visual alert indicators to table rows, and a popup to view/delete all alerts.

## 5a. Alert indicator on rows

- Rows for stocks that have active alerts: prepend `🔔` before the direction arrow
  (or change the direction cell to show `🔔↑` instead of just `↑`)
- Updated on every `update_quote()` call

## 5b. Alert list popup

- Key `v` → modal `ListView` showing all alert rules
- Each row: `代码 名称  类型          阈值    状态`
  - Example: `hk00700 腾讯控股  price_above  436.00  待触发`
  - Status: `待触发` (armed) or `已触发` (triggered, waiting for re-arm)
- Key `d` in popup → delete selected alert
- Key `escape` → close popup
- Deletion persists to config.yaml via `save_alerts()`

## Done when

- [ ] Rows with alerts show 🔔 indicator
- [ ] `v` opens alert list popup with all current alerts
- [ ] `d` deletes selected alert
- [ ] `escape` closes popup cleanly
- [ ] Deletions are persisted to config.yaml
