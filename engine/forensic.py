#!/usr/bin/env python3
"""
STAR — Forensic stock analyst. Surfaces red flags most investors skip.

Built on REAL data (yfinance): insider transactions, 5y financial statements,
ISS-style governance risk scores, and SEC filing list. Each flag cites the
actual figure/source and a severity. A weighted risk score (0-100) is produced.

HONESTY: some of the 8 categories are not auto-detectable from structured data
and require reading the 10-K text. Those are reported as "REVIEW" items with a
link to the latest 10-K rather than fabricated findings:
  • Promoter Pledges      → N/A for US listings (India/NSE disclosure concept)
  • Related Party Txns    → 10-K notes (REVIEW)
  • Notes to Accounts     → 10-K notes (REVIEW)
  • Auditor opinion text  → 10-K (we use ISS auditRisk as a proxy signal)
"""
from datetime import datetime, timezone, timedelta

import pandas as pd
import yfinance as yf

SEV_WEIGHT = {"HIGH": 25, "MED": 12, "LOW": 5}


def _row(df, *names):
    if df is None or getattr(df, "empty", True):
        return None
    for n in names:
        if n in df.index:
            return df.loc[n]
    for idx in df.index:
        if any(n.lower() in str(idx).lower() for n in names):
            return df.loc[idx]
    return None


def _val(series, i=0):
    try:
        v = float(series.iloc[i])
        return v if v == v else None
    except Exception:
        return None


def analyze(ticker):
    t = yf.Ticker(ticker)
    try:
        info = t.info or {}
    except Exception:
        info = {}
    name = info.get("longName") or info.get("shortName") or ticker.upper()

    flags = []  # each: {category, severity, evidence, explanation}
    reviews = []  # filing-based items we can't auto-detect

    inc = _safe(lambda: t.income_stmt)
    bs = _safe(lambda: t.balance_sheet)
    cf = _safe(lambda: t.cashflow)

    # ---------- 1. INSIDER SELLING ----------
    try:
        it = t.insider_transactions
        if it is not None and not it.empty and "Start Date" in it.columns:
            recent = it.copy()
            recent["Start Date"] = pd.to_datetime(recent["Start Date"], errors="coerce")
            cutoff = pd.Timestamp(datetime.now() - timedelta(days=180))
            recent = recent[recent["Start Date"] >= cutoff]
            txt = recent["Transaction"].astype(str).str.lower()
            sales = recent[txt.str.contains("sale|sell|disposed")]
            buys = recent[txt.str.contains("purchase|buy|acqui")]
            sale_val = float(sales["Value"].fillna(0).sum())
            buy_val = float(buys["Value"].fillna(0).sum())
            if sale_val > 0 and sale_val > 3 * max(buy_val, 1):
                sev = "HIGH" if sale_val > 5e7 else "MED"
                top = sales.sort_values("Value", ascending=False).head(1)
                who = top["Insider"].iloc[0] if not top.empty else "insiders"
                flags.append({
                    "category": "Insider Selling", "severity": sev,
                    "evidence": f"${sale_val/1e6:.1f}M sold vs ${buy_val/1e6:.1f}M bought (last 6mo); "
                                f"{len(sales)} sale txns, largest by {who}",
                    "explanation": "Heavy net insider selling can signal management lacks "
                                   "conviction in near-term prospects.",
                })
            elif buy_val > sale_val and buy_val > 0:
                flags.append({"category": "Insider Selling", "severity": "LOW",
                    "evidence": f"Net insider BUYING ${buy_val/1e6:.1f}M vs ${sale_val/1e6:.1f}M sold (6mo)",
                    "explanation": "Net insider buying — a positive signal (informational)."})
    except Exception:
        pass

    # ---------- 2. PROMOTER PLEDGES ----------
    reviews.append({"category": "Promoter Pledges", "status": "N/A",
                    "note": "Promoter share-pledge disclosure is an India/NSE concept; "
                            "not applicable to US-listed companies."})

    # ---------- 3. ACCOUNTING IRREGULARITIES (accruals + Beneish-lite) ----------
    try:
        ni = _row(inc, "Net Income")
        ta = _row(bs, "Total Assets")
        ocf = _row(cf, "Operating Cash Flow", "Total Cash From Operating Activities")
        if ni is not None and ta is not None and ocf is not None:
            accruals = (_val(ni) - _val(ocf))
            ratio = accruals / _val(ta) if _val(ta) else None
            if ratio is not None and ratio > 0.10:
                sev = "HIGH" if ratio > 0.20 else "MED"
                flags.append({"category": "Accounting Irregularities", "severity": sev,
                    "evidence": f"Accruals ratio {ratio*100:.1f}% — Net income ${_val(ni)/1e9:.2f}B "
                                f"vs operating cash flow ${_val(ocf)/1e9:.2f}B",
                    "explanation": "Earnings materially exceed cash generation (high accruals) — "
                                   "a classic earnings-quality / aggressive-recognition red flag."})
    except Exception:
        pass

    # ---------- 4. FINANCIAL STATEMENT RED FLAGS ----------
    _fin_flags(inc, bs, cf, info, flags)

    # ---------- 5. HIDDEN GOVERNANCE RISKS (ISS scores + concentration) ----------
    try:
        for tag, label in [("overallRisk", "Overall"), ("boardRisk", "Board"),
                           ("compensationRisk", "Compensation"),
                           ("shareHolderRightsRisk", "Shareholder rights")]:
            r = info.get(tag)
            if isinstance(r, (int, float)) and r >= 8:
                flags.append({"category": "Hidden Governance Risks",
                    "severity": "HIGH" if r >= 9 else "MED",
                    "evidence": f"ISS {label} risk score {int(r)}/10",
                    "explanation": f"High {label.lower()} governance risk (10 = worst decile)."})
        insiders = info.get("heldPercentInsiders")
        if isinstance(insiders, (int, float)) and insiders > 0.5:
            flags.append({"category": "Hidden Governance Risks", "severity": "MED",
                "evidence": f"Insiders hold {insiders*100:.0f}% of shares",
                "explanation": "High insider ownership concentration can limit minority shareholder influence."})
    except Exception:
        pass

    # ---------- 6/7/8. AUDITOR / RELATED PARTY / NOTES (filing review) ----------
    audit = info.get("auditRisk")
    if isinstance(audit, (int, float)) and audit >= 8:
        flags.append({"category": "Auditor Warnings", "severity": "MED",
            "evidence": f"ISS audit risk score {int(audit)}/10",
            "explanation": "Elevated audit-risk score; review the 10-K auditor's report for "
                           "going-concern language or material weaknesses."})
    latest_10k = None
    try:
        for f in (t.sec_filings or []):
            if str(f.get("type", "")).startswith("10-K"):
                latest_10k = f.get("edgarUrl"); break
    except Exception:
        pass
    for cat in ["Auditor Warnings", "Related Party Transactions", "Notes to Accounts"]:
        reviews.append({"category": cat, "status": "REVIEW",
            "note": f"Not auto-detectable from structured data — requires reading the latest 10-K notes."
                    + (f" Latest 10-K: {latest_10k}" if latest_10k else "")})

    # ---------- SCORE ----------
    # sum severity weights; a "LOW" insider-buying note is positive, not a risk
    raw = sum(SEV_WEIGHT.get(f["severity"], 0) for f in flags
              if not (f["category"] == "Insider Selling" and f["severity"] == "LOW"))
    score = min(raw, 100)
    if score >= 70:
        rating = "HIGH RISK"
    elif score >= 45:
        rating = "ELEVATED"
    elif score >= 20:
        rating = "MODERATE"
    else:
        rating = "LOW RISK"

    high = sum(1 for f in flags if f["severity"] == "HIGH")
    med = sum(1 for f in flags if f["severity"] == "MED")
    summary = (f"{len([f for f in flags if not (f['category']=='Insider Selling' and f['severity']=='LOW')])} "
               f"red flags ({high} high, {med} medium). "
               + ("Warrants deeper investigation before investing." if score >= 45
                  else "No major structured red flags, but always review the 10-K notes."))

    return {
        "symbol": ticker.upper(), "name": name,
        "risk_score": score, "rating": rating, "summary": summary,
        "flags": flags, "reviews": reviews,
        "latest_10k": latest_10k,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
    }


def _safe(fn):
    try:
        return fn()
    except Exception:
        return None


def _fin_flags(inc, bs, cf, info, flags):
    # margin trend (latest vs prior)
    try:
        rev = _row(inc, "Total Revenue")
        ni = _row(inc, "Net Income")
        if rev is not None and ni is not None and len(rev) >= 2:
            m0 = _val(ni, 0) / _val(rev, 0)
            m1 = _val(ni, 1) / _val(rev, 1)
            if m0 is not None and m1 is not None and m0 < m1 - 0.05:
                flags.append({"category": "Financial Statement Red Flags", "severity": "MED",
                    "evidence": f"Net margin fell {m1*100:.1f}% → {m0*100:.1f}% YoY",
                    "explanation": "Deteriorating profitability."})
            # revenue decline
            if _val(rev, 0) is not None and _val(rev, 1) and _val(rev, 0) < _val(rev, 1):
                flags.append({"category": "Financial Statement Red Flags", "severity": "MED",
                    "evidence": f"Revenue declined ${_val(rev,1)/1e9:.1f}B → ${_val(rev,0)/1e9:.1f}B",
                    "explanation": "Top-line contraction."})
    except Exception:
        pass
    # leverage
    try:
        debt = _row(bs, "Total Debt")
        eq = _row(bs, "Stockholders Equity", "Common Stock Equity")
        if debt is not None and eq is not None and _val(eq):
            de = _val(debt) / _val(eq)
            if de > 2:
                flags.append({"category": "Financial Statement Red Flags",
                    "severity": "HIGH" if de > 4 else "MED",
                    "evidence": f"Debt/Equity {de:.1f}x (debt ${_val(debt)/1e9:.1f}B / equity ${_val(eq)/1e9:.1f}B)",
                    "explanation": "High leverage increases solvency risk."})
    except Exception:
        pass
    # earnings quality: OCF vs NI
    try:
        ni = _row(inc, "Net Income"); ocf = _row(cf, "Operating Cash Flow", "Total Cash From Operating Activities")
        if ni is not None and ocf is not None and _val(ni) and _val(ni) > 0:
            if _val(ocf) < 0.6 * _val(ni):
                flags.append({"category": "Financial Statement Red Flags", "severity": "MED",
                    "evidence": f"Operating CF ${_val(ocf)/1e9:.2f}B is <60% of net income ${_val(ni)/1e9:.2f}B",
                    "explanation": "Profits not converting to cash — earnings quality concern."})
    except Exception:
        pass
    # dilution
    try:
        so = _row(bs, "Share Issued", "Ordinary Shares Number")
        if so is not None and len(so) >= 2 and _val(so, 1):
            g = (_val(so, 0) - _val(so, 1)) / _val(so, 1)
            if g > 0.10:
                flags.append({"category": "Financial Statement Red Flags", "severity": "MED",
                    "evidence": f"Shares outstanding +{g*100:.0f}% YoY",
                    "explanation": "Significant shareholder dilution."})
    except Exception:
        pass
    # liquidity
    try:
        ca = _row(bs, "Current Assets", "Total Current Assets")
        cl = _row(bs, "Current Liabilities", "Total Current Liabilities")
        if ca is not None and cl is not None and _val(cl):
            cr = _val(ca) / _val(cl)
            if cr < 1:
                flags.append({"category": "Financial Statement Red Flags",
                    "severity": "HIGH" if cr < 0.7 else "MED",
                    "evidence": f"Current ratio {cr:.2f} (assets ${_val(ca)/1e9:.1f}B / liab ${_val(cl)/1e9:.1f}B)",
                    "explanation": "Current liabilities exceed current assets — liquidity strain."})
    except Exception:
        pass


if __name__ == "__main__":
    import sys, json
    r = analyze(sys.argv[1] if len(sys.argv) > 1 else "NVDA")
    print(f"\n{r['symbol']} — {r['name']}")
    print(f"RISK SCORE: {r['risk_score']}/100  [{r['rating']}]")
    print(f"{r['summary']}\n")
    for f in r["flags"]:
        print(f"  [{f['severity']:4}] {f['category']}: {f['evidence']}")
    print("\nREVIEW (filing-based):")
    for rv in r["reviews"]:
        print(f"  ({rv['status']}) {rv['category']}")
