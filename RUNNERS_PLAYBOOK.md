# STAR — Low-Float Momentum Runner Playbook (SME core)

> Our chosen edge. This is a **discipline document**, not a hype sheet. In this
> arena you don't win by being right more often — you win by **not getting
> destroyed** on the trades you're wrong about. 90% of the edge is what you
> REFUSE to trade. Account: ~$500 (Webull, shares). Last updated 2026-06-15.

---

## 1. What we're hunting (and why)

A "runner" is a **low-float, small/micro-cap** stock that gaps and trends hard on
a catalyst because there are few shares available and a flood of buyers. Low float
= little supply = violent moves in BOTH directions.

Real drivers:
- **Float** (shares actually tradeable): <20M is explosive, <10M is dynamite.
  Float, not market cap, is what makes it move.
- **Relative volume**: today's volume vs normal. <3x = not in play. 5x+ = in play.
- **Catalyst**: PR, earnings, FDA, contract, social/squeeze. No catalyst = no edge.
- **% gain + price**: $1–$20 is the sweet spot. Sub-$1 = manipulation/delisting zone.

## 2. The brutal truth about this arena

These are the **most manipulated names in the market**. The company is often the
counterparty: micro-caps do **ATM / S-1 share offerings INTO strength** — they
print new shares and sell them into your buying, capping the move and crushing the
price. A name up 190% by 10am is frequently a **pump being distributed to retail.**
This is why CAST showing "0 forensic flags" was a *data gap, not safety* —
yfinance has no fundamentals on these, so the real risk lives in SEC filings
(check for recent S-1, 424B5, ATM facility, reverse split history on the SEC site).

## 3. The runner lifecycle (know where you are in the day)

| Stage | What it looks like | Our action |
|-------|--------------------|-----------|
| **Pre-market gap** | Gapping up on news + premarket volume | Build watchlist, mark levels |
| **Opening drive** | First 5–15 min, huge volume, breaks PM high | Setup A (early breakout) |
| **Parabolic / blow-off** | Vertical, far above VWAP, at HOD, +100%+ | **DO NOT BUY. This is the trap.** |
| **First pullback** | Fades to VWAP / rising MA, volume cools, holds | Setup B (pullback continuation) |
| **Fade / breakdown** | Loses VWAP, lower highs, sellers in control | Stand aside (or advanced short) |
| **Afternoon** | Usually dead/choppy unless 2nd catalyst | Mostly avoid |

## 4. The ONLY setups we take (long, $500 account)

- **Setup A — Opening breakout:** in play early (rel vol high), breaks the
  premarket high / first 5-min high WITH volume, **not yet extended** (near the
  break level, not +100% above it). Enter on the break, stop under the breakout.
- **Setup B — First pullback (preferred):** after an initial spike, price pulls
  back to VWAP or a rising MA on **declining** volume and holds, then resumes.
  Enter on the reclaim, stop under the pullback low. Best reward:risk of the day.

That's it. Two setups. Everything else is "no."

## 5. Hard rules (break one = you lose the account)

1. **NEVER chase.** No buying a name already extended far above VWAP / at HOD
   after a parabolic move. If it's up 100%+ and at the highs, it's a watch, not a buy.
2. **ALWAYS have a stop, set BEFORE entry.** No mental stops on runners — they
   gap against you. Hard stop in the platform.
3. **Risk per trade ≤ $25 (5% of $500).** Position size = $25 ÷ (entry − stop).
   The stop distance sets the size, never the other way around.
4. **Daily max loss = $50 (10%).** Hit it → done for the day. No revenge trades.
5. **No sub-$1 stocks, no nano-caps (<$30M)** unless explicitly accepting ruin risk.
6. **Take profits into strength.** Sell half into the spike; trail the rest. These
   round-trip fast — a +30% winner becomes a loser if you get greedy.
7. **One position at a time** at this account size. Focus beats diversification here.
8. **If you didn't plan the entry/stop/target before the bell, you don't take it.**

## 6. Position-size math (memorize)

```
risk_dollars   = 25                      # 5% of 500, hard cap
stop_distance  = entry - stop            # in $ per share
shares         = floor(risk_dollars / stop_distance)
cost           = shares * entry          # must be <= buying power
```
Example: entry $4.00, stop $3.60 → risk/share $0.40 → 62 shares → $248 cost,
$25 at risk. If filled and stopped, you lose $25, not your account.

## 7. How we validate before risking real money

We can't cleanly backtest intraday runners with free daily data. So:
- **`engine/runner_grader.py`** grades live movers by lifecycle stage + gives a
  playbook verdict (WATCH-EARLY / PULLBACK-WATCH / DO-NOT-CHASE / AVOID-LANDMINE).
- **Paper/journal first.** Log every would-be trade (setup, entry, stop, target,
  outcome) for 2–3 weeks. Only trade real size once the journal shows the rules
  produce positive expectancy *in your hands*. Discipline is the variable, not the
  setup.

## 8. Daily routine

1. Pre-market: pull movers (Runner Scanner), filter for float <20M, rel vol >3x,
   price $1–$20, real catalyst. Drop the landmines.
2. For survivors: check SEC filings for a recent offering/ATM (dilution kills runs).
3. Mark levels: PM high, prior close, VWAP.
4. At the open: wait. Take only Setup A or B. Chase nothing.
5. Size by the risk formula. Hard stop in. Sell into strength.
6. Hit daily max loss → stop. Journal every trade.
