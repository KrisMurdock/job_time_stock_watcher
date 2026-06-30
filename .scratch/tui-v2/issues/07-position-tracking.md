# 07 — Position tracking (cost + quantity → P&L)

Status: 📋 todo  
Labels: feature, phase-3

## Summary

Lightweight position tracking: user inputs cost and quantity per stock; system
computes and displays P&L.

## Config format (new `positions` key in config.yaml)

```yaml
positions:
  hk00700:
    cost: 420.0    # 买入均价
    quantity: 200  # 持仓数量(股)
```

## Position model

`Position(cost: float, quantity: int)` dataclass.
`AppConfig.positions: dict[str, Position]`, loaded from config.

## P&L columns in main table (after existing columns)

| 列 | 含义 | 公式 | 格式 |
|----|------|------|------|
| 持仓量 | shares held | — | `int` |
| 成本价 | avg cost | — | `8.2f` |
| 市值 | market value | `price × quantity` | `10.2f` |
| 盈亏 | P&L amount | `(price-cost) × quantity` | `+8.2f`, red/green |
| 盈亏比 | P&L% | `(price-cost)/cost × 100` | `+6.2f%%`, red/green |

Columns show `—` when stock has no position.
P&L computed on every quote update.

## Input UI

- Key `p` on highlighted row → prompt: `成本 数量` (e.g. `1680 100`)
- Validate: cost > 0, quantity > 0 integer
- Empty input → delete position for that stock
- Persist immediately via `save_positions()` (new function, pattern like `save_watchlist`)

## Done when

- [ ] `Position` dataclass in models.py
- [ ] `positions` key parsed from config.yaml
- [ ] P&L computation on quote update
- [ ] 5 new columns added to table (hidden when no positions exist)
- [ ] `p` key input for cost + quantity
- [ ] Config persistence via `save_positions()`
- [ ] Tests for P&L calculation
