---
updated: 2026-06-27T13:43:43.609514
tags: [dashboard]
---
# 📊 STAR — Visual Dashboard  #dashboard

**All-time:** +$13.38 · **Today:** +$0.00 · **Win rate:** 47.9% · **Trades:** 73

> [!info] Needs the **Obsidian Charts** community plugin to render these as graphs.

## Equity curve (cumulative P&L)

```chart
type: line
labels: ['2026-06-18', '2026-06-23', '2026-06-24', '2026-06-25', '2026-06-26']
series:
  - title: Cumulative $
    data: [26.78, 55.78, 69.74, 87.24, 13.38]
tension: 0.3
fill: true
width: 80%
beginAtZero: true
```

## Daily P&L

```chart
type: bar
labels: ['2026-06-18', '2026-06-23', '2026-06-24', '2026-06-25', '2026-06-26']
series:
  - title: Daily P&L
    data: [26.78, 29.0, 13.96, 17.5, -73.86]
colors: ['#2ee6a6', '#2ee6a6', '#2ee6a6', '#2ee6a6', '#ff5d6c']
width: 80%
beginAtZero: true
```

## P&L by strategy

```chart
type: bar
labels: ['scalp', 'gold', 'fvg', 'option', 'stock']
series:
  - title: P&L $
    data: [83.21, 0.0, -2.38, -32.0, -35.45]
colors: ['#2ee6a6', '#2ee6a6', '#ff5d6c', '#ff5d6c', '#ff5d6c']
width: 70%
beginAtZero: true
```

## Win rate by strategy (%)

```chart
type: bar
labels: ['scalp', 'gold', 'fvg', 'option', 'stock']
series:
  - title: Win %
    data: [49.1, 66.7, 33.3, 60.0, 55.6]
width: 70%
beginAtZero: true
```
