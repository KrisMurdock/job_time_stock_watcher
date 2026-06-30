# 09 — Detail panel (order book + extended info)

Status: 📋 todo  
Labels: feature, phase-4

## Summary

A popup panel showing extended information for the highlighted stock, including
5-level order book for A-shares and PE/market cap for HK stocks.

## Trigger

Key `enter` on highlighted row → modal overlay.

## Content

```
┌─ hk00700 腾讯控股 ──────────────────────────┐
│                                                │
│  当前价   436.50  [+1.25%]                     │
│  今开     431.00  最高 438.00  最低 430.20    │
│  成交量   3899万股  成交额 166.88亿            │
│                                                │
│  [A-share only: 5-level order book]            │
│  卖5  438.00   12,000    │                     │
│  卖4  437.80    8,500    │                     │
│  卖3  437.50   15,200    │                     │
│  卖2  437.20    3,100    │                     │
│  卖1  437.00   22,000    │                     │
│  ───────────────────────  │                     │
│  买1  436.50   18,500    │                     │
│  买2  436.20    6,200    │                     │
│  买3  436.00   11,000    │                     │
│  买4  435.80    4,800    │                     │
│  买5  435.50   14,300    │                     │
│                                                │
│  [HK only]                                    │
│  市盈率  15.73  总市值 39147.41亿              │
│                                                │
│  [Recent alerts for this stock]                │
│  14:25  price_above 436.00 → 436.50           │
│  11:02  price_above 436.00 → 436.20           │
│                                                │
│  [enter/escape 关闭]                           │
└────────────────────────────────────────────────┘
```

## Behavior

- Opens centered modal
- Content auto-updates when new quotes arrive for that stock
- `enter` or `escape` closes
- Up/down arrow keys while open: move highlight in main table behind modal

## Done when

- [ ] `enter` on highlighted row opens detail panel
- [ ] Shows price, open, high, low, volume, turnover
- [ ] A-share: 5-level bid/ask order book
- [ ] HK: PE + market cap
- [ ] Recent alert history for that stock (last 10)
- [ ] Auto-refresh on new quotes
- [ ] `escape` / `enter` closes
