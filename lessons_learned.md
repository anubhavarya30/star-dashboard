# Lessons Learned — Algorithmic Trading Playbook

*Star's working knowledge base. Original synthesis of widely-taught principles
from quantitative-trading and trader-psychology literature — Ernest Chan,
Perry Kaufman, and the "Market Wizards" interviews — plus modern systematic
best practices. Concepts are paraphrased in my own words for operational use.*

---

## 1. Mean-Reversion vs. Momentum (Ernest Chan)

- **Markets are either mean-reverting or trending — rarely both at once.** Test
  which regime an instrument is in *before* choosing a strategy. A mean-reversion
  model applied to a trending market (or vice-versa) is a reliable way to lose.
- **Stationarity matters.** Mean-reversion edges come from a price series (or a
  spread/pair) that is statistically stationary. Use tests like ADF or the
  Hurst exponent to check before trusting a reversion signal.
- **Half-life of reversion** sets the holding period. Estimate it (e.g. via an
  Ornstein-Uhlenbeck fit) and size your stop/timeout accordingly.
- **Pairs / cointegration** turn two non-stationary assets into one tradeable
  stationary spread. For our gold book, miners (NEM) vs. bullion (GLD/XAUUSD)
  is a natural candidate spread to monitor for divergence.
- **Backtest honesty:** beware look-ahead bias, survivorship bias, and
  data-snooping. A Sharpe that only exists in-sample is noise.

## 2. Position Sizing & Risk of Ruin

- **Kelly criterion** gives the growth-optimal bet fraction, but full-Kelly is
  too volatile for live trading. Use **fractional Kelly (¼–½)** to cut drawdowns.
- Cap **risk per trade** to a small, fixed fraction of equity (commonly
  0.5–2%). This is the single most important survival rule.
- Track **risk of ruin** as a function of win rate, payoff ratio, and bet size —
  not just expected return.

## 3. Adaptive Trend Systems (Perry Kaufman)

- **Adaptive moving averages** (e.g. Kaufman's Adaptive Moving Average, KAMA)
  speed up in trends and slow down in chop using an *efficiency ratio*
  (net change ÷ sum of absolute changes). Fixed-length MAs whipsaw in noise.
- **Match the tool to volatility.** Normalize signals and stops by volatility
  (ATR) so the same logic behaves consistently across regimes and instruments.
- **Robustness over optimization.** A parameter that works across a broad
  plateau of values beats a single knife-edge "optimal" value that is curve-fit.
- **Diversify by strategy *and* by timeframe**, not just by symbol — uncorrelated
  return streams smooth the equity curve.

## 4. Trader Psychology & Discipline (Market Wizards themes)

- **Cut losses quickly; let winners run.** Asymmetric payoff (small losses, large
  wins) lets a sub-50% win rate still be highly profitable.
- **Always define the exit before entering.** No position without a pre-set stop
  *and* target — this is hard-wired into our order logic.
- **Risk management beats prediction.** The best traders attribute survival to
  controlling losses, not to being right often.
- **Avoid revenge trading.** After a loss, step back and analyze the setup; do
  not immediately re-enter to "win it back."
- **Consistency and process** matter more than any single trade. Judge decisions
  by whether they followed the plan, not only by their outcome.

## 5. Systematic / Algo Best Practices

- **Walk-forward validation** and out-of-sample testing; never deploy on
  in-sample fit alone.
- **Model transaction costs, slippage, and borrow** explicitly — many paper
  edges evaporate after costs.
- **Regime awareness:** monitor volatility and correlation regimes; reduce size
  or stand aside when conditions fall outside the model's tested envelope.
- **Multi-timeframe confirmation:** require alignment (e.g. 1h *and* 4h) before
  acting, to filter low-quality signals.
- **Fail safe, not silent:** every agent logs its state; errors degrade to a
  flat/no-trade default rather than guessing.

---

## Star's Operating Rules (derived)

1. Trade only the 5 approved NYSE symbols; everything else stays off the board.
2. Every entry ships with a stop **and** a target; target R:R ≥ ~1.5.
3. Risk per trade is volatility-scaled via ATR and capped as a % of equity.
4. Confirm direction on at least two timeframes before execution.
5. After each losing trade, write a root cause + lesson to the `mistakes` table
   and refuse to repeat the same setup signature.
6. Prefer fractional-Kelly sizing; never full-Kelly.
7. Treat backtests as hypotheses, not promises — validate walk-forward.

*This file is read live by the dashboard's "Lessons & Mistakes" page and is
appended to as the system learns.*
