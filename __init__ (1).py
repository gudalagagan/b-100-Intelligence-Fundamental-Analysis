"""
data_service.py
===============
Reads clean CSVs once at startup and caches them in memory.
All views import from here — no database needed for the demo.
"""
import os, re
import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

def _load(name):
    path = os.path.join(DATA_DIR, name)
    return pd.read_csv(path) if os.path.exists(path) else pd.DataFrame()

# ── Load once ──────────────────────────────────────────────────────────────
companies_df    = _load("companies.csv")
balancesheet_df = _load("balancesheet.csv")
pl_df           = _load("profitandloss.csv")
cashflow_df     = _load("cashflow.csv")
analysis_df     = _load("analysis.csv")
prosandcons_df  = _load("prosandcons.csv")
documents_df    = _load("documents.csv")
sector_df       = _load("sector_mapping.csv")

# Rename 'id' → 'symbol' in companies
if "id" in companies_df.columns:
    companies_df = companies_df.rename(columns={"id": "symbol"})

# Add sector to companies if missing
if "sector" not in companies_df.columns and not sector_df.empty:
    companies_df = companies_df.merge(sector_df, on="symbol", how="left")

def _safe(val):
    """Convert NaN/inf to None."""
    if val is None: return None
    try:
        if np.isnan(val) or np.isinf(val): return None
    except Exception: pass
    return val

def _round(val, n=2):
    v = _safe(val)
    return round(float(v), n) if v is not None else None

# ── Health score (simple rule-based, no ML library needed) ─────────────────
def compute_health_score(symbol):
    """Return 0-100 score and label for a company based on key metrics."""
    pl = pl_df[pl_df["company_id"] == symbol].copy()
    bs = balancesheet_df[balancesheet_df["company_id"] == symbol].copy()
    cf = cashflow_df[cashflow_df["company_id"] == symbol].copy()

    score = 50.0  # baseline

    # Remove TTM rows for scoring
    pl = pl[pl["year"] != "TTM"]
    if pl.empty:
        return score, "AVERAGE"

    pl = pl.sort_values("sort_order")
    latest_pl = pl.iloc[-1]

    # 1. Profitability (25 pts)
    opm = _safe(latest_pl.get("opm_percentage"))
    npm = _safe(latest_pl.get("net_profit_margin_pct"))
    prof_score = 0
    if opm is not None:
        prof_score += min(opm / 30 * 15, 15)   # max 15 pts at OPM≥30%
    if npm is not None:
        prof_score += min(npm / 20 * 10, 10)   # max 10 pts at NPM≥20%
    score += prof_score - 12.5   # centre around 0

    # 2. Leverage (20 pts) - lower D/E = better
    if not bs.empty:
        bs = bs.sort_values("sort_order")
        latest_bs = bs.iloc[-1]
        de = _safe(latest_bs.get("debt_to_equity"))
        if de is not None:
            if de == 0:
                score += 10
            elif de < 0.5:
                score += 7
            elif de < 1.0:
                score += 4
            elif de < 2.0:
                score += 0
            else:
                score -= 8

    # 3. Cash flow (15 pts)
    if not cf.empty:
        cf_clean = cf[cf["year"] != "TTM"].sort_values("sort_order")
        if not cf_clean.empty:
            last_cf = cf_clean.iloc[-1]
            ocf = _safe(last_cf.get("operating_activity"))
            fcf = _safe(last_cf.get("free_cash_flow"))
            if ocf is not None and ocf > 0:
                score += 5
            if fcf is not None and fcf > 0:
                score += 5

    # 4. Revenue growth (20 pts)
    if len(pl) >= 3:
        rev_vals = pl["sales"].dropna()
        if len(rev_vals) >= 3:
            old = rev_vals.iloc[-4] if len(rev_vals) >= 4 else rev_vals.iloc[0]
            new = rev_vals.iloc[-1]
            if old > 0:
                cagr = ((new / old) ** (1/3) - 1) * 100
                score += min(cagr / 15 * 10, 10)

    # Clamp to 0-100
    score = max(0, min(100, score))

    if score >= 85:   label = "EXCELLENT"
    elif score >= 70: label = "GOOD"
    elif score >= 50: label = "AVERAGE"
    elif score >= 35: label = "WEAK"
    else:             label = "POOR"

    return round(score, 1), label

LABEL_COLOR = {
    "EXCELLENT": "#2ECC71",
    "GOOD":      "#27AE60",
    "AVERAGE":   "#F39C12",
    "WEAK":      "#E67E22",
    "POOR":      "#E74C3C",
}
LABEL_BG = {
    "EXCELLENT": "#d5f5e3",
    "GOOD":      "#a9dfbf",
    "AVERAGE":   "#fde8c8",
    "WEAK":      "#fad5b0",
    "POOR":      "#fadbd8",
}

# ── Public API ─────────────────────────────────────────────────────────────
def get_all_companies():
    """Return list of company dicts with score attached."""
    out = []
    for _, row in companies_df.iterrows():
        sym = str(row["symbol"]).strip()
        score, label = compute_health_score(sym)
        out.append({
            "symbol":       sym,
            "company_name": str(row.get("company_name","")).strip(),
            "sector":       str(row.get("sector","Other")).strip(),
            "logo":         str(row.get("company_logo","")).strip(),
            "website":      str(row.get("website","")).strip(),
            "roce":         _round(row.get("roce_percentage")),
            "roe":          _round(row.get("roe_percentage")),
            "health_score": score,
            "health_label": label,
            "label_color":  LABEL_COLOR.get(label, "#999"),
            "label_bg":     LABEL_BG.get(label, "#eee"),
        })
    return sorted(out, key=lambda x: x["health_score"], reverse=True)

def get_company(symbol):
    """Full data for one company."""
    sym = symbol.upper().strip()
    row = companies_df[companies_df["symbol"] == sym]
    if row.empty:
        return None
    row = row.iloc[0]

    score, label = compute_health_score(sym)

    # P&L history (exclude TTM for charts)
    pl = pl_df[(pl_df["company_id"] == sym) & (pl_df["year"] != "TTM")].sort_values("sort_order")
    cf = cashflow_df[(cashflow_df["company_id"] == sym) & (cashflow_df["year"] != "TTM")].sort_values("sort_order")
    bs = balancesheet_df[(balancesheet_df["company_id"] == sym) & (balancesheet_df["year"] != "TTM")].sort_values("sort_order")

    # Latest metrics
    latest_pl = pl.iloc[-1] if not pl.empty else pd.Series()
    latest_bs = bs.iloc[-1] if not bs.empty else pd.Series()

    # Pros & cons
    pc = prosandcons_df[prosandcons_df["company_id"] == sym] if not prosandcons_df.empty else pd.DataFrame()
    pros = pc[pc["is_pro"] == True]["text"].tolist() if not pc.empty and "is_pro" in pc.columns else []
    cons = pc[pc["is_pro"] == False]["text"].tolist() if not pc.empty and "is_pro" in pc.columns else []

    # Documents
    docs = []
    if not documents_df.empty:
        d = documents_df[documents_df["company_id"] == sym].dropna(subset=["annual_report_url"])
        docs = d.sort_values("year", ascending=False)[["year","annual_report_url"]].to_dict("records")

    return {
        "symbol":       sym,
        "company_name": str(row.get("company_name","")).strip(),
        "sector":       str(row.get("sector","Other")).strip(),
        "logo":         str(row.get("company_logo","")).strip(),
        "website":      str(row.get("website","")).strip(),
        "nse_profile":  str(row.get("nse_profile","")).strip(),
        "bse_profile":  str(row.get("bse_profile","")).strip(),
        "about":        str(row.get("about_company","")).strip(),
        "face_value":   _round(row.get("face_value")),
        "book_value":   _round(row.get("book_value")),
        "roce":         _round(row.get("roce_percentage")),
        "roe":          _round(row.get("roe_percentage")),
        "health_score": score,
        "health_label": label,
        "label_color":  LABEL_COLOR.get(label,"#999"),
        "label_bg":     LABEL_BG.get(label,"#eee"),
        "latest_sales":  _round(latest_pl.get("sales")),
        "latest_profit": _round(latest_pl.get("net_profit")),
        "latest_opm":    _round(latest_pl.get("opm_percentage")),
        "latest_eps":    _round(latest_pl.get("eps")),
        "latest_de":     _round(latest_bs.get("debt_to_equity")),
        "pros": pros,
        "cons": cons,
        "documents": docs,
    }

def get_chart_data(symbol):
    """All chart data for a company detail page."""
    sym = symbol.upper().strip()
    pl = pl_df[(pl_df["company_id"] == sym) & (pl_df["year"] != "TTM")].sort_values("sort_order")
    cf = cashflow_df[(cashflow_df["company_id"] == sym) & (cashflow_df["year"] != "TTM")].sort_values("sort_order")
    bs = balancesheet_df[(balancesheet_df["company_id"] == sym) & (balancesheet_df["year"] != "TTM")].sort_values("sort_order")
    ana = analysis_df[analysis_df["company_id"] == sym] if not analysis_df.empty else pd.DataFrame()

    def col(df, c):
        if c not in df.columns: return []
        return [_round(v) for v in df[c].tolist()]

    years    = pl["year"].tolist()
    cf_years = cf["year"].tolist()
    bs_years = bs["year"].tolist()

    # CAGR data
    cagr = {"10Y":{},"5Y":{},"3Y":{},"TTM":{}}
    if not ana.empty:
        for _, r in ana.iterrows():
            p = str(r.get("period",""))
            m = str(r.get("metric",""))
            v = _round(r.get("value_pct"))
            if p in cagr:
                cagr[p][m] = v

    score, label = compute_health_score(sym)

    return {
        "years":  years,
        "sales":  col(pl, "sales"),
        "net_profit": col(pl, "net_profit"),
        "opm":    col(pl, "opm_percentage"),
        "eps":    col(pl, "eps"),
        "dividend": col(pl, "dividend_payout"),
        "npm":    col(pl, "net_profit_margin_pct"),

        "cf_years":   cf_years,
        "operating":  col(cf, "operating_activity"),
        "investing":  col(cf, "investing_activity"),
        "financing":  col(cf, "financing_activity"),
        "fcf":        col(cf, "free_cash_flow"),
        "ccr":        col(cf, "cash_conversion_ratio"),

        "bs_years":   bs_years,
        "borrowings": col(bs, "borrowings"),
        "reserves":   col(bs, "reserves"),
        "equity_cap": col(bs, "equity_capital"),
        "fixed_assets": col(bs, "fixed_assets"),
        "investments":  col(bs, "investments"),
        "other_assets": col(bs, "other_asset"),
        "total_assets": col(bs, "total_assets"),
        "de_ratio":   col(bs, "debt_to_equity"),

        "cagr": cagr,
        "health_score": score,
        "health_label": label,
    }

def get_sectors():
    """All sectors with company count and avg metrics."""
    all_co = get_all_companies()
    from collections import defaultdict
    sector_data = defaultdict(list)
    for c in all_co:
        sector_data[c["sector"]].append(c)
    result = []
    for sector, companies in sorted(sector_data.items()):
        scores = [c["health_score"] for c in companies]
        result.append({
            "sector":        sector,
            "company_count": len(companies),
            "avg_score":     round(sum(scores)/len(scores), 1) if scores else 0,
            "top_company":   companies[0]["company_name"] if companies else "",
            "companies":     companies,
        })
    return sorted(result, key=lambda x: x["avg_score"], reverse=True)

def get_sector(name):
    sectors = get_sectors()
    for s in sectors:
        if s["sector"].upper() == name.upper():
            return s
    return None

def search_companies(query):
    q = query.lower().strip()
    all_co = get_all_companies()
    return [c for c in all_co
            if q in c["symbol"].lower() or q in c["company_name"].lower()]

def get_screener_results(filters):
    """Apply financial filters and return matching companies."""
    all_co = get_all_companies()
    results = []
    for c in all_co:
        sym = c["symbol"]
        pl = pl_df[(pl_df["company_id"] == sym) & (pl_df["year"] != "TTM")].sort_values("sort_order")
        bs = balancesheet_df[(balancesheet_df["company_id"] == sym) & (balancesheet_df["year"] != "TTM")].sort_values("sort_order")

        latest_pl = pl.iloc[-1] if not pl.empty else pd.Series()
        latest_bs = bs.iloc[-1] if not bs.empty else pd.Series()

        roe  = _safe(latest_pl.get("return_on_assets"))
        de   = _safe(latest_bs.get("debt_to_equity"))
        opm  = _safe(latest_pl.get("opm_percentage"))

        # Apply filters
        if filters.get("min_roe") and (roe is None or roe < float(filters["min_roe"])): continue
        if filters.get("max_de")  and (de  is None or de  > float(filters["max_de"])): continue
        if filters.get("min_opm") and (opm is None or opm < float(filters["min_opm"])): continue
        if filters.get("sector")  and filters["sector"] != c["sector"]: continue
        if filters.get("label")   and filters["label"]  != c["health_label"]: continue
        if filters.get("min_score") and c["health_score"] < float(filters["min_score"]): continue

        results.append({**c, "roe": _round(roe), "de": _round(de), "opm": _round(opm)})
    return results
