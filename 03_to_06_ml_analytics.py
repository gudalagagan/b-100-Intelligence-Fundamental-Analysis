"""
Notebook 2 — Financial Health Scoring Engine
=============================================
Builds the 6-dimension scoring model, runs it on all 100 companies,
validates results, and exports scores to CSV.

Run: python notebooks/02_health_scoring.py
"""

import os
import warnings
import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")

DATA   = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "clean")
OUT    = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "clean")

# ── Load data ──────────────────────────────────────────────────────────────
companies = pd.read_csv(f"{DATA}/companies.csv")
pl        = pd.read_csv(f"{DATA}/profitandloss.csv")
bs        = pd.read_csv(f"{DATA}/balancesheet.csv")
cf        = pd.read_csv(f"{DATA}/cashflow.csv")
analysis  = pd.read_csv(f"{DATA}/analysis.csv")

if "id" in companies.columns:
    companies = companies.rename(columns={"id": "symbol"})

pl_hist = pl[pl["year"] != "TTM"].copy()
bs_hist = bs[bs["year"] != "TTM"].copy()
cf_hist = cf[cf["year"] != "TTM"].copy()


def safe(val):
    if val is None: return np.nan
    try:
        f = float(val)
        return np.nan if (np.isnan(f) or np.isinf(f)) else f
    except Exception:
        return np.nan


# ── SCORING DIMENSIONS ─────────────────────────────────────────────────────

def score_profitability(sym):
    """25% weight. Based on OPM%, net profit margin, ROE consistency."""
    rows = pl_hist[pl_hist["company_id"] == sym].sort_values("sort_order")
    if rows.empty: return 50.0

    opm_vals = rows["opm_percentage"].dropna()
    npm_vals  = rows["net_profit_margin_pct"].dropna()

    score = 50.0
    if not opm_vals.empty:
        avg_opm = opm_vals.mean()
        score += min((avg_opm / 25) * 25, 25)   # up to +25 at OPM ≥ 25%
        score -= max(0, -avg_opm) * 3             # penalty for negative OPM

    if not npm_vals.empty:
        avg_npm = npm_vals.mean()
        score += min((avg_npm / 20) * 15, 15)

    # Consistency bonus: std dev of OPM
    if len(opm_vals) >= 3:
        opm_std = opm_vals.std()
        if opm_std < 5: score += 5
        elif opm_std > 15: score -= 5

    return max(0, min(100, score))


def score_growth(sym):
    """20% weight. Revenue and profit CAGR over 3Y and 5Y."""
    ana = analysis[analysis["company_id"] == sym]
    score = 50.0

    for period, weight in [("3Y", 15), ("5Y", 10), ("10Y", 5)]:
        cagr_row = ana[(ana["metric"] == "compounded_sales_growth") & (ana["period"] == period)]
        if not cagr_row.empty:
            v = safe(cagr_row["value_pct"].values[0])
            if v is not None and not np.isnan(v):
                if v > 15:    score += weight * 1.0
                elif v > 10:  score += weight * 0.7
                elif v > 5:   score += weight * 0.4
                elif v > 0:   score += weight * 0.1
                else:         score -= weight * 0.5

    return max(0, min(100, score))


def score_leverage(sym):
    """20% weight. D/E ratio, interest coverage, debt trend."""
    bs_rows = bs_hist[bs_hist["company_id"] == sym].sort_values("sort_order")
    pl_rows = pl_hist[pl_hist["company_id"] == sym].sort_values("sort_order")
    if bs_rows.empty: return 50.0

    score = 70.0  # start optimistic — most companies have some debt
    latest_bs = bs_rows.iloc[-1]
    de = safe(latest_bs.get("debt_to_equity"))

    if de is not None:
        if de == 0:      score = 100
        elif de < 0.3:   score = 90
        elif de < 0.5:   score = 80
        elif de < 1.0:   score = 70
        elif de < 2.0:   score = 55
        elif de < 3.0:   score = 40
        elif de < 5.0:   score = 25
        else:            score = 10

    # Interest coverage bonus/penalty
    if not pl_rows.empty:
        latest_pl = pl_rows.iloc[-1]
        ic = safe(latest_pl.get("interest_coverage"))
        if ic is not None:
            if ic > 10:  score += 5
            elif ic < 2: score -= 15
            elif ic < 1: score -= 25

    return max(0, min(100, score))


def score_cashflow(sym):
    """15% weight. Operating cash flow quality, FCF, CCR."""
    cf_rows = cf_hist[cf_hist["company_id"] == sym].sort_values("sort_order")
    pl_rows = pl_hist[pl_hist["company_id"] == sym].sort_values("sort_order")
    if cf_rows.empty: return 50.0

    score = 50.0
    # Count years with positive operating CF
    ocf = cf_rows["operating_activity"].dropna()
    if not ocf.empty:
        pos_pct = (ocf > 0).mean()
        score += pos_pct * 25  # up to +25 if always positive

    # FCF quality
    fcf = cf_rows["free_cash_flow"].dropna()
    if not fcf.empty:
        pos_fcf = (fcf > 0).mean()
        score += pos_fcf * 15

    # Cash conversion ratio (CCR > 1 = good)
    if "cash_conversion_ratio" in cf_rows.columns:
        ccr = cf_rows["cash_conversion_ratio"].dropna()
        if not ccr.empty:
            avg_ccr = ccr.mean()
            if avg_ccr > 1.2:   score += 10
            elif avg_ccr > 1.0: score += 5
            elif avg_ccr < 0:   score -= 15

    return max(0, min(100, score))


def score_dividend(sym):
    """10% weight. Dividend consistency and payout sustainability."""
    rows = pl_hist[pl_hist["company_id"] == sym].sort_values("sort_order")
    if rows.empty: return 50.0

    div = rows["dividend_payout"].dropna() if "dividend_payout" in rows.columns else pd.Series()
    score = 40.0

    if not div.empty:
        paying_pct = (div > 0).mean()
        score += paying_pct * 30  # up to +30 if always pays

        avg_payout = div[div > 0].mean() if (div > 0).any() else 0
        if avg_payout > 30:  score += 15
        elif avg_payout > 15: score += 8
        elif avg_payout > 5:  score += 4

    # Zero dividend is not automatically penalised (growth cos reinvest)
    return max(0, min(100, score))


def score_trend(sym):
    """10% weight. Direction of revenue/profit over last 3 years."""
    rows = pl_hist[pl_hist["company_id"] == sym].sort_values("sort_order").tail(5)
    if len(rows) < 3: return 50.0

    score = 50.0
    rev = rows["sales"].dropna()
    if len(rev) >= 3:
        slope, _, r, _, _ = stats.linregress(range(len(rev)), rev)
        if slope > 0 and r > 0.7:  score += 25    # strong uptrend
        elif slope > 0:            score += 12    # weak uptrend
        elif slope < 0:            score -= 15    # downtrend

    profit = rows["net_profit"].dropna()
    if len(profit) >= 3:
        slope2, _, _, _, _ = stats.linregress(range(len(profit)), profit)
        if slope2 > 0: score += 10
        else:          score -= 10

    return max(0, min(100, score))


# ── WEIGHTS ────────────────────────────────────────────────────────────────
WEIGHTS = {
    "profitability": 0.25,
    "growth":        0.20,
    "leverage":      0.20,
    "cashflow":      0.15,
    "dividend":      0.10,
    "trend":         0.10,
}


def compute_score(sym):
    sub = {
        "profitability": score_profitability(sym),
        "growth":        score_growth(sym),
        "leverage":      score_leverage(sym),
        "cashflow":      score_cashflow(sym),
        "dividend":      score_dividend(sym),
        "trend":         score_trend(sym),
    }
    total = sum(sub[k] * WEIGHTS[k] for k in sub)
    total = max(0, min(100, total))

    if total >= 85:   label = "EXCELLENT"
    elif total >= 70: label = "GOOD"
    elif total >= 50: label = "AVERAGE"
    elif total >= 35: label = "WEAK"
    else:             label = "POOR"

    return {**sub, "overall_score": round(total, 2), "health_label": label}


def main():
    print("="*60)
    print("NOTEBOOK 2 — FINANCIAL HEALTH SCORING")
    print("="*60 + "\n")

    symbols = companies["symbol"].unique().tolist()
    print(f"Scoring {len(symbols)} companies...\n")

    results = []
    for sym in symbols:
        r = compute_score(sym)
        results.append({"symbol": sym, **r})

    df = pd.DataFrame(results)

    # ── Results summary ────────────────────────────────────
    print("Score distribution:")
    print(df["health_label"].value_counts().to_string())
    print(f"\nOverall score stats:")
    print(df["overall_score"].describe().round(2).to_string())

    print("\nTop 10:")
    print(df.nlargest(10, "overall_score")[["symbol","overall_score","health_label"]].to_string(index=False))

    print("\nBottom 10:")
    print(df.nsmallest(10, "overall_score")[["symbol","overall_score","health_label"]].to_string(index=False))

    # ── Sensitivity analysis ───────────────────────────────
    print("\n" + "="*60)
    print("SENSITIVITY ANALYSIS — How weights affect rankings")
    print("="*60)

    base_top5 = df.nlargest(5, "overall_score")["symbol"].tolist()
    print(f"Base weights top 5: {base_top5}")

    # Increase profitability weight
    alt_scores = []
    for _, row in df.iterrows():
        alt = (row["profitability"]*0.40 + row["growth"]*0.20 +
               row["leverage"]*0.15 + row["cashflow"]*0.10 +
               row["dividend"]*0.10 + row["trend"]*0.05)
        alt_scores.append(round(alt, 2))
    df["alt_score"] = alt_scores
    alt_top5 = df.nlargest(5, "alt_score")["symbol"].tolist()
    print(f"Profitability-heavy (40%) top 5: {alt_top5}")

    overlap = len(set(base_top5) & set(alt_top5))
    print(f"Overlap: {overlap}/5 companies → score is {'stable' if overlap>=4 else 'sensitive'}")

    # ── Validation against known companies ────────────────
    print("\n" + "="*60)
    print("VALIDATION — Do scores match expectations?")
    print("="*60)
    check = ["TCS", "HDFCBANK", "INFY", "WIPRO", "ADANIPOWER", "BHEL"]
    for sym in check:
        row = df[df["symbol"] == sym]
        if not row.empty:
            r = row.iloc[0]
            print(f"  {sym:15} score={r['overall_score']:5.1f}  {r['health_label']:10}")

    # ── Export ─────────────────────────────────────────────
    from datetime import datetime
    df["computed_at"] = datetime.now().isoformat()
    out_path = f"{OUT}/ml_scores.csv"
    df.to_csv(out_path, index=False)
    print(f"\n✓ Scores exported to: {out_path}")


if __name__ == "__main__":
    main()
