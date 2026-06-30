# 08 — Extended data columns (open/volume/turnover/PE/market cap)

Status: 📋 todo  
Labels: feature, phase-4

## Summary

Display the additional fields parsed in issue #03 as optional columns.

## New columns

| Column | Key | Format | Markets | Default visibility |
|--------|-----|--------|:---:|:---:|
| 今开 | `open` | `8.2f` | A + HK | show |
| 成交量 | `volume` | `12.0f` | A + HK | show |
| 成交额 | `turnover` | `10.2f` 亿 | A + HK | hide |
| 市盈率 | `pe` | `6.2f` | HK only | show for HK |
| 总市值 | `market_cap` | `8.2f` 亿 | HK only | show for HK |

- Volume format: raw shares (e.g. `111135281` → `1.11亿` for readability)
- Turnover format: yuan (e.g. `11.21亿`)
- Market cap: already 亿 from API
- Columns show `—` when data unavailable

## Column visibility config

```yaml
table_columns: [dir, code, name, price, change_pct, change_amount, open, high, low, volume]
```

Optional; if absent, show all supported columns. Column keys match the programmatic
keys from issue #04 (not the display labels). User can reorder/omit columns by
editing this list.

## Done when

- [ ] 5 new columns rendered in StockTable.update_quote()
- [ ] Volume formatted as 亿/万 for readability
- [ ] Configurable column list in config.yaml
- [ ] Hot-reload picks up column changes
- [ ] No PE/market_cap columns for A-share stocks (show `—`)
