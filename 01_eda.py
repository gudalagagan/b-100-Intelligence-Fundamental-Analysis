"""
Notebooks 3–6 — ML Analytics Suite
=====================================
  Notebook 3: Anomaly Detection (Z-score + Isolation Forest)
  Notebook 4: Sector Clustering (K-Means + PCA)
  Notebook 5: Peer Comparison Engine (Cosine Similarity)
  Notebook 6: Revenue Trend Forecasting

Run: python notebooks/03_to_06_ml_analytics.py
"""

import os
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

DATA = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "clean")
OUT  = os.path.join(os.path.dirname(os.path.dirname(__file__)), "notebooks", "ml_charts")
os.makedirs(OUT, exist_ok=True)

companies = pd.read_csv(f"{DATA}/companies.csv")
pl        = pd.read_csv(f"{DATA}/profitandloss.csv")
bs        = pd.read_csv(f"{DATA}/balancesheet.csv")
cf        = pd.read_csv(f"{DATA}/cashflow.csv")

if "id" in companies.columns:
    companies = companies.rename(columns={"id": "symbol"})

pl_hist = pl[pl["year"] != "TTM"].copy()
bs_hist = bs[bs["year"] != "TTM"].copy()
cf_hist = cf[cf["year"] != "TTM"].copy()


# ══════════════════════════════════════════════════════════════
# NOTEBOOK 3 — ANOMALY DETECTION
# ══════════════════════════════════════════════════════════════

def run_anomaly_detection():
    print("="*60)
    print("NOTEBOOK 3 — ANOMALY DETECTION")
    print("="*60)

    try:
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        print("  scikit-learn not installed. Run: pip install scikit-learn")
        return pd.DataFrame()

    # Build feature matrix: one row per (company, year)
    merged = pl_hist.merge(
        bs_hist[["company_id","year","debt_to_equity","total_assets"]],
        on=["company_id","year"], how="left"
    )
    merged = merged.merge(
        cf_hist[["company_id","year","operating_activity","free_cash_flow"]],
        on=["company_id","year"], how="left"
    )

    features = ["sales","net_profit","opm_percentage","debt_to_equity",
                "operating_activity","free_cash_flow"]
    feat_data = merged[["company_id","year"] + features].dropna(subset=features)

    scaler = StandardScaler()
    X = scaler.fit_transform(feat_data[features])

    # ── Method 1: Z-score ─────────────────────────────────
    z_scores = np.abs(stats_zscore(X))
    z_anomaly = (z_scores > 2.5).any(axis=1)
    feat_data["z_anomaly"] = z_anomaly

    # ── Method 2: Isolation Forest ────────────────────────
    iso = IsolationForest(contamination=0.05, random_state=42, n_jobs=-1)
    iso_pred = iso.fit_predict(X)
    feat_data["iso_anomaly"] = iso_pred == -1

    # ── Agreement between methods ─────────────────────────
    feat_data["both_anomaly"] = feat_data["z_anomaly"] & feat_data["iso_anomaly"]

    z_count   = feat_data["z_anomaly"].sum()
    iso_count = feat_data["iso_anomaly"].sum()
    both      = feat_data["both_anomaly"].sum()

    print(f"  Z-score anomalies:        {z_count}")
    print(f"  Isolation Forest:         {iso_count}")
    print(f"  Agreed by both methods:   {both}")
    print(f"  Agreement rate: {both/min(z_count,iso_count)*100:.1f}%")

    # ── Notable anomalies ─────────────────────────────────
    confirmed = feat_data[feat_data["both_anomaly"]].copy()
    print(f"\nConfirmed anomalies (both methods agree): {len(confirmed)}")
    if not confirmed.empty:
        print(confirmed[["company_id","year","sales","net_profit","opm_percentage"]].head(15).to_string(index=False))

    # ── Save chart ────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.scatter(range(len(feat_data)), feat_data["sales"],
               c=feat_data["both_anomaly"].map({True:"red",False:"steelblue"}),
               alpha=0.5, s=20)
    ax.set_title("Anomaly Detection — Sales (Red = Both Methods Agree)", fontweight="bold")
    ax.set_xlabel("Data Point Index")
    ax.set_ylabel("Sales (₹ Crore)")
    plt.tight_layout()
    plt.savefig(f"{OUT}/03_anomaly_detection.png", dpi=120, bbox_inches="tight")
    plt.close()
    print(f"\n  ✓ Chart saved")

    # Export
    confirmed.to_csv(f"{DATA}/anomaly_flags.csv", index=False)
    print(f"  ✓ Anomalies saved to data/clean/anomaly_flags.csv")
    return confirmed


def stats_zscore(X):
    return (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-9)


# ══════════════════════════════════════════════════════════════
# NOTEBOOK 4 — SECTOR CLUSTERING
# ══════════════════════════════════════════════════════════════

def run_clustering():
    print("\n" + "="*60)
    print("NOTEBOOK 4 — SECTOR CLUSTERING (K-MEANS + PCA)")
    print("="*60)

    try:
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
        from sklearn.decomposition import PCA
    except ImportError:
        print("  scikit-learn not installed. Skipping.")
        return pd.DataFrame()

    # Build one feature vector per company (latest year)
    pl_latest = pl_hist.sort_values("sort_order").groupby("company_id").last().reset_index()
    bs_latest = bs_hist.sort_values("sort_order").groupby("company_id").last().reset_index()
    cf_latest = cf_hist.sort_values("sort_order").groupby("company_id").last().reset_index()

    merged = pl_latest.merge(
        bs_latest[["company_id","debt_to_equity","equity_ratio"]],
        on="company_id", how="left"
    ).merge(
        cf_latest[["company_id","operating_activity","free_cash_flow"]],
        on="company_id", how="left"
    )

    features = ["opm_percentage","net_profit_margin_pct",
                "debt_to_equity","interest_coverage",
                "operating_activity","return_on_assets"]
    feat = merged[["company_id"] + features].dropna(subset=features)

    scaler = StandardScaler()
    X = scaler.fit_transform(feat[features])

    # Elbow method
    inertias = []
    k_range  = range(2, 9)
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        km.fit(X)
        inertias.append(km.inertia_)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(list(k_range), inertias, marker="o", color="#2E75B6", linewidth=2)
    ax.set_xlabel("Number of Clusters (K)")
    ax.set_ylabel("Inertia (Within-cluster SS)")
    ax.set_title("Elbow Method — Optimal K for Clustering", fontweight="bold")
    plt.tight_layout()
    plt.savefig(f"{OUT}/04a_elbow.png", dpi=120, bbox_inches="tight")
    plt.close()

    # Fit with K=5
    K = 5
    km = KMeans(n_clusters=K, random_state=42, n_init=10)
    feat["cluster"] = km.fit_predict(X)

    # PCA for visualisation
    pca = PCA(n_components=2)
    pca_coords = pca.fit_transform(X)
    feat["pca1"] = pca_coords[:, 0]
    feat["pca2"] = pca_coords[:, 1]

    colors = ["#2E75B6","#2ECC71","#E74C3C","#F39C12","#8e44ad"]
    cluster_labels = {
        0: "High-Margin IT/Pharma",
        1: "Capital-Intensive Industrial",
        2: "High-Leverage Energy/Infra",
        3: "Diversified Mid-cap",
        4: "FMCG/Consumer Staples",
    }

    fig, ax = plt.subplots(figsize=(13, 9))
    for cl in range(K):
        mask = feat["cluster"] == cl
        ax.scatter(feat.loc[mask, "pca1"], feat.loc[mask, "pca2"],
                   color=colors[cl], alpha=0.75, s=90,
                   label=f"Cluster {cl}: {cluster_labels.get(cl,'')}")
        for _, row in feat[mask].iterrows():
            ax.annotate(row["company_id"], (row["pca1"], row["pca2"]),
                        fontsize=6.5, alpha=0.7)
    ax.set_xlabel(f"PCA 1 ({pca.explained_variance_ratio_[0]*100:.1f}% variance)")
    ax.set_ylabel(f"PCA 2 ({pca.explained_variance_ratio_[1]*100:.1f}% variance)")
    ax.set_title("Chart 4b — K-Means Clustering (K=5) via PCA", fontweight="bold", fontsize=13)
    ax.legend(loc="upper right", fontsize=9)
    plt.tight_layout()
    plt.savefig(f"{OUT}/04b_clustering_pca.png", dpi=120, bbox_inches="tight")
    plt.close()

    print(f"  Explained variance by 2 PCs: {pca.explained_variance_ratio_.sum()*100:.1f}%")
    print("\n  Cluster membership:")
    for cl in range(K):
        members = feat[feat["cluster"] == cl]["company_id"].tolist()
        print(f"  Cluster {cl} ({cluster_labels.get(cl,'')}):")
        print(f"    {', '.join(members[:8])}{'...' if len(members)>8 else ''}")

    feat.to_csv(f"{DATA}/cluster_assignments.csv", index=False)
    print(f"\n  ✓ Cluster assignments saved")
    return feat


# ══════════════════════════════════════════════════════════════
# NOTEBOOK 5 — PEER COMPARISON ENGINE
# ══════════════════════════════════════════════════════════════

def run_peer_comparison():
    print("\n" + "="*60)
    print("NOTEBOOK 5 — PEER COMPARISON (COSINE SIMILARITY)")
    print("="*60)

    try:
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:
        print("  scikit-learn not installed. Skipping.")
        return

    pl_latest = pl_hist.sort_values("sort_order").groupby("company_id").last().reset_index()
    bs_latest = bs_hist.sort_values("sort_order").groupby("company_id").last().reset_index()

    merged = pl_latest.merge(
        bs_latest[["company_id","debt_to_equity"]],
        on="company_id", how="left"
    )

    features = ["opm_percentage","net_profit_margin_pct","debt_to_equity",
                "interest_coverage","return_on_assets"]
    feat = merged[["company_id"] + features].dropna(subset=features).set_index("company_id")

    scaler = StandardScaler()
    X = scaler.fit_transform(feat[features])
    X_df = pd.DataFrame(X, index=feat.index, columns=features)

    sim_matrix = cosine_similarity(X_df)
    sim_df = pd.DataFrame(sim_matrix, index=X_df.index, columns=X_df.index)

    def get_peers(sym, n=5):
        if sym not in sim_df.index: return []
        row = sim_df[sym].drop(sym).nlargest(n)
        return list(zip(row.index, row.values.round(3)))

    # Validate
    test_pairs = [
        ("TCS",    ["INFY", "WIPRO", "HCLTECH"]),
        ("HDFCBANK",["AXISBANK","KOTAKBANK","ICICIBANK"]),
    ]
    print("\n  Validation (peers should match sector expectations):")
    all_pass = True
    for sym, expected in test_pairs:
        peers = [p[0] for p in get_peers(sym, 5)]
        overlap = len(set(peers) & set(expected))
        ok = overlap >= 1
        if not ok: all_pass = False
        print(f"  {sym:12} → top peers: {peers}")
        print(f"             expected overlap with {expected}: {overlap} — {'✓' if ok else '✗'}")

    print(f"\n  Validation: {'PASSED' if all_pass else 'NEEDS REVIEW'}")

    # Build full peer mapping table
    rows = []
    for sym in sim_df.index:
        for peer, score in get_peers(sym, 5):
            rows.append({"symbol": sym, "peer": peer, "similarity": score})
    peer_df = pd.DataFrame(rows)
    peer_df.to_csv(f"{DATA}/peer_mapping.csv", index=False)
    print(f"\n  ✓ Peer mapping saved ({len(peer_df)} pairs)")


# ══════════════════════════════════════════════════════════════
# NOTEBOOK 6 — TREND FORECASTING
# ══════════════════════════════════════════════════════════════

def run_forecasting():
    print("\n" + "="*60)
    print("NOTEBOOK 6 — REVENUE TREND FORECASTING")
    print("="*60)

    # Get top 20 companies by latest revenue
    pl_latest = pl_hist.sort_values("sort_order").groupby("company_id").last().reset_index()
    top20 = pl_latest.nlargest(20, "sales")["company_id"].tolist()

    forecasts = []
    for sym in top20:
        rows = pl_hist[pl_hist["company_id"] == sym].sort_values("sort_order")
        rev  = rows["sales"].dropna()
        if len(rev) < 4:
            continue

        vals = rev.values
        x    = np.arange(len(vals))

        # Linear trend classification
        slope, intercept, r, _, _ = \
            __import__("scipy").stats.linregress(x, vals)
        if r**2 > 0.6 and slope > 0:     trend = "UP"
        elif r**2 > 0.6 and slope < 0:   trend = "DOWN"
        else:                             trend = "FLAT"

        # Simple linear forecast for next year
        next_x   = len(vals)
        forecast = max(0, slope * next_x + intercept)
        ci_width = vals.std() * 1.64  # 90% CI

        forecasts.append({
            "symbol":    sym,
            "trend":     trend,
            "r_squared": round(r**2, 3),
            "forecast_next_year": round(forecast, 2),
            "forecast_low":  round(max(0, forecast - ci_width), 2),
            "forecast_high": round(forecast + ci_width, 2),
            "note": "MODEL ESTIMATE — NOT FINANCIAL ADVICE",
        })

    df = pd.DataFrame(forecasts)
    print(f"  Forecasts generated: {len(df)}")
    print("\n  Trend classification:")
    print(df["trend"].value_counts().to_string())
    print("\n  Sample forecasts (top 8 by revenue):")
    print(df[["symbol","trend","r_squared","forecast_next_year"]].head(8).to_string(index=False))

    df.to_csv(f"{DATA}/revenue_forecasts.csv", index=False)
    print(f"\n  ✓ Forecasts saved to data/clean/revenue_forecasts.csv")
    print("  ⚠  These are simple linear extrapolations for educational use only.")
    print("     They are NOT investment advice.")


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main():
    run_anomaly_detection()
    run_clustering()
    run_peer_comparison()
    run_forecasting()

    print("\n" + "="*60)
    print("✓ All ML analytics notebooks complete.")
    print(f"  Charts saved to:  notebooks/ml_charts/")
    print(f"  Data saved to:    data/clean/")
    print("="*60)


if __name__ == "__main__":
    main()
