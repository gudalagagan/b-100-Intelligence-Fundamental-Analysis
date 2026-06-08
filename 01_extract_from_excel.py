"""
ETL Script 3 — Load to PostgreSQL Data Warehouse
=================================================
Creates the star-schema tables and loads all clean data.
Run AFTER scripts 01 and 02.

Prerequisites:
  pip install psycopg2-binary sqlalchemy pandas python-decouple

Configure DB connection via environment or .env file:
  DATABASE_URL=postgresql://user:password@localhost:5432/bluestock_dw

Run:  python etl/03_load_to_warehouse.py
"""

import os
import sys
import numpy as np
import pandas as pd

# ── Config ─────────────────────────────────────────────────────────────────
# Try python-decouple first (best practice), fall back to env var, then default
try:
    from decouple import config
    DB_URL = config("DATABASE_URL", default="postgresql://postgres:postgres@localhost:5432/bluestock_dw")
except ImportError:
    DB_URL = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/bluestock_dw"
    )

CLEAN_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "clean")

# ── SQL DDL (star schema) ───────────────────────────────────────────────────
SCHEMA_SQL = """
-- ── DIMENSION TABLES ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS dim_sector (
    sector_id   SERIAL PRIMARY KEY,
    sector_name VARCHAR(100) UNIQUE NOT NULL,
    sector_code VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS dim_health_label (
    label_id    SERIAL PRIMARY KEY,
    label_name  VARCHAR(20) UNIQUE NOT NULL,
    min_score   NUMERIC(5,2) NOT NULL,
    max_score   NUMERIC(5,2) NOT NULL,
    color_hex   VARCHAR(7) NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_company (
    symbol          VARCHAR(30) PRIMARY KEY,
    company_name    TEXT,
    sector          VARCHAR(100),
    company_logo    TEXT,
    chart_link      TEXT,
    about_company   TEXT,
    website         TEXT,
    nse_profile     TEXT,
    bse_profile     TEXT,
    face_value      NUMERIC(10,2),
    book_value      NUMERIC(10,2),
    roce_percentage NUMERIC(10,4),
    roe_percentage  NUMERIC(10,4)
);

CREATE TABLE IF NOT EXISTS dim_year (
    year_id     SERIAL PRIMARY KEY,
    year_label  VARCHAR(20) UNIQUE NOT NULL,
    fiscal_year INTEGER,
    quarter     VARCHAR(5),
    is_ttm      BOOLEAN DEFAULT FALSE,
    sort_order  INTEGER
);

-- ── FACT TABLES ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS fact_profit_loss (
    id                      SERIAL PRIMARY KEY,
    symbol                  VARCHAR(30) REFERENCES dim_company(symbol),
    year_label              VARCHAR(20),
    sales                   NUMERIC(20,2),
    expenses                NUMERIC(20,2),
    operating_profit        NUMERIC(20,2),
    opm_pct                 NUMERIC(10,4),
    other_income            NUMERIC(20,2),
    interest                NUMERIC(20,2),
    depreciation            NUMERIC(20,2),
    profit_before_tax       NUMERIC(20,2),
    tax_pct                 NUMERIC(10,4),
    net_profit              NUMERIC(20,2),
    eps                     NUMERIC(15,4),
    dividend_payout_pct     NUMERIC(10,4),
    net_profit_margin_pct   NUMERIC(10,4),
    expense_ratio_pct       NUMERIC(10,4),
    interest_coverage       NUMERIC(15,4),
    asset_turnover          NUMERIC(15,6),
    return_on_assets        NUMERIC(10,4),
    sort_order              INTEGER,
    UNIQUE (symbol, year_label)
);

CREATE TABLE IF NOT EXISTS fact_balance_sheet (
    id                  SERIAL PRIMARY KEY,
    symbol              VARCHAR(30) REFERENCES dim_company(symbol),
    year_label          VARCHAR(20),
    equity_capital      NUMERIC(20,2),
    reserves            NUMERIC(20,2),
    borrowings          NUMERIC(20,2),
    other_liabilities   NUMERIC(20,2),
    total_liabilities   NUMERIC(20,2),
    fixed_assets        NUMERIC(20,2),
    cwip                NUMERIC(20,2),
    investments         NUMERIC(20,2),
    other_asset         NUMERIC(20,2),
    total_assets        NUMERIC(20,2),
    debt_to_equity      NUMERIC(15,6),
    equity_ratio        NUMERIC(15,6),
    sort_order          INTEGER,
    UNIQUE (symbol, year_label)
);

CREATE TABLE IF NOT EXISTS fact_cash_flow (
    id                      SERIAL PRIMARY KEY,
    symbol                  VARCHAR(30) REFERENCES dim_company(symbol),
    year_label              VARCHAR(20),
    operating_activity      NUMERIC(20,2),
    investing_activity      NUMERIC(20,2),
    financing_activity      NUMERIC(20,2),
    net_cash_flow           NUMERIC(20,2),
    free_cash_flow          NUMERIC(20,2),
    cash_conversion_ratio   NUMERIC(15,6),
    sort_order              INTEGER,
    UNIQUE (symbol, year_label)
);

CREATE TABLE IF NOT EXISTS fact_analysis (
    id                          SERIAL PRIMARY KEY,
    symbol                      VARCHAR(30) REFERENCES dim_company(symbol),
    metric                      VARCHAR(60),
    period                      VARCHAR(10),
    value_pct                   NUMERIC(10,4),
    UNIQUE (symbol, metric, period)
);

CREATE TABLE IF NOT EXISTS fact_ml_scores (
    id                  SERIAL PRIMARY KEY,
    symbol              VARCHAR(30) REFERENCES dim_company(symbol),
    computed_at         TIMESTAMP DEFAULT NOW(),
    overall_score       NUMERIC(6,2),
    profitability_score NUMERIC(6,2),
    growth_score        NUMERIC(6,2),
    leverage_score      NUMERIC(6,2),
    cashflow_score      NUMERIC(6,2),
    dividend_score      NUMERIC(6,2),
    trend_score         NUMERIC(6,2),
    health_label        VARCHAR(20),
    UNIQUE (symbol, computed_at)
);

CREATE TABLE IF NOT EXISTS fact_pros_cons (
    id              SERIAL PRIMARY KEY,
    symbol          VARCHAR(30) REFERENCES dim_company(symbol),
    is_pro          BOOLEAN,
    text            TEXT,
    source          VARCHAR(20) DEFAULT 'MANUAL',
    confidence      NUMERIC(5,4),
    generated_at    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fact_documents (
    id                  SERIAL PRIMARY KEY,
    symbol              VARCHAR(30) REFERENCES dim_company(symbol),
    year                INTEGER,
    annual_report_url   TEXT,
    UNIQUE (symbol, year)
);

-- ── INDEXES ────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_pl_symbol ON fact_profit_loss(symbol);
CREATE INDEX IF NOT EXISTS idx_pl_year ON fact_profit_loss(year_label);
CREATE INDEX IF NOT EXISTS idx_bs_symbol ON fact_balance_sheet(symbol);
CREATE INDEX IF NOT EXISTS idx_cf_symbol ON fact_cash_flow(symbol);
CREATE INDEX IF NOT EXISTS idx_scores_symbol ON fact_ml_scores(symbol);
"""

# ── Seed data for health labels ─────────────────────────────────────────────
HEALTH_LABELS = [
    {"label_name": "EXCELLENT", "min_score": 85.0, "max_score": 100.0, "color_hex": "#2ECC71"},
    {"label_name": "GOOD",      "min_score": 70.0, "max_score": 84.9,  "color_hex": "#27AE60"},
    {"label_name": "AVERAGE",   "min_score": 50.0, "max_score": 69.9,  "color_hex": "#F39C12"},
    {"label_name": "WEAK",      "min_score": 35.0, "max_score": 49.9,  "color_hex": "#E67E22"},
    {"label_name": "POOR",      "min_score": 0.0,  "max_score": 34.9,  "color_hex": "#E74C3C"},
]


def get_engine():
    """Create SQLAlchemy engine. Exits with helpful message if psycopg2 missing."""
    try:
        from sqlalchemy import create_engine, text
        return create_engine(DB_URL), text
    except ImportError:
        print("✗  sqlalchemy not installed. Run: pip install sqlalchemy psycopg2-binary")
        sys.exit(1)


def create_schema(engine, text):
    """Run the DDL to create all tables."""
    print("  Creating schema...")
    with engine.begin() as conn:
        conn.execute(text(SCHEMA_SQL))
    print("  ✓  Schema created (or already exists).")


def load_dim_companies(engine, text):
    df = pd.read_csv(os.path.join(CLEAN_DIR, "companies.csv"))
    df = df.rename(columns={"id": "symbol"})
    # Deduplicate
    df = df.drop_duplicates(subset=["symbol"], keep="first")

    rows = df.to_dict("records")
    with engine.begin() as conn:
        for r in rows:
            conn.execute(text("""
                INSERT INTO dim_company
                    (symbol, company_name, sector, company_logo, chart_link,
                     about_company, website, nse_profile, bse_profile,
                     face_value, book_value, roce_percentage, roe_percentage)
                VALUES
                    (:symbol, :company_name, :sector, :company_logo, :chart_link,
                     :about_company, :website, :nse_profile, :bse_profile,
                     :face_value, :book_value, :roce_percentage, :roe_percentage)
                ON CONFLICT (symbol) DO UPDATE SET
                    company_name    = EXCLUDED.company_name,
                    sector          = EXCLUDED.sector,
                    company_logo    = EXCLUDED.company_logo,
                    about_company   = EXCLUDED.about_company,
                    website         = EXCLUDED.website,
                    roce_percentage = EXCLUDED.roce_percentage,
                    roe_percentage  = EXCLUDED.roe_percentage
            """), _clean_row(r))
    print(f"  ✓  dim_company: {len(rows)} rows")


def load_dim_sectors(engine, text):
    df = pd.read_csv(os.path.join(CLEAN_DIR, "sector_mapping.csv"))
    sectors = df["sector"].dropna().unique().tolist()
    with engine.begin() as conn:
        for s in sectors:
            conn.execute(text("""
                INSERT INTO dim_sector (sector_name, sector_code)
                VALUES (:sector_name, :sector_code)
                ON CONFLICT (sector_name) DO NOTHING
            """), {"sector_name": s, "sector_code": s[:10].upper()})
    print(f"  ✓  dim_sector: {len(sectors)} sectors")


def load_dim_health_labels(engine, text):
    with engine.begin() as conn:
        for label in HEALTH_LABELS:
            conn.execute(text("""
                INSERT INTO dim_health_label (label_name, min_score, max_score, color_hex)
                VALUES (:label_name, :min_score, :max_score, :color_hex)
                ON CONFLICT (label_name) DO NOTHING
            """), label)
    print(f"  ✓  dim_health_label: {len(HEALTH_LABELS)} labels")


def load_dim_years(engine, text):
    """Build dim_year from all unique year values across fact tables."""
    import re
    years = set()
    for fname in ["balancesheet.csv", "profitandloss.csv", "cashflow.csv"]:
        df = pd.read_csv(os.path.join(CLEAN_DIR, fname))
        years.update(df["year"].dropna().unique().tolist())

    rows = []
    for y in sorted(years, key=lambda x: 99999 if x == "TTM" else int(re.search(r"\d{4}", str(x)).group()) * 100 + {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,"Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}.get(str(x)[:3], 0) if re.search(r"\d{4}", str(x)) else 0):
        is_ttm = (str(y).upper() == "TTM")
        m = re.match(r"([A-Za-z]{3})\s+(\d{4})", str(y))
        fiscal_year = int(m.group(2)) if m else None
        sort_order = 99999 if is_ttm else (fiscal_year * 100 + {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,"Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}.get(m.group(1) if m else "", 0)) if fiscal_year else 0
        rows.append({
            "year_label": str(y), "fiscal_year": fiscal_year,
            "is_ttm": is_ttm, "sort_order": sort_order
        })

    with engine.begin() as conn:
        for r in rows:
            conn.execute(text("""
                INSERT INTO dim_year (year_label, fiscal_year, is_ttm, sort_order)
                VALUES (:year_label, :fiscal_year, :is_ttm, :sort_order)
                ON CONFLICT (year_label) DO NOTHING
            """), r)
    print(f"  ✓  dim_year: {len(rows)} year labels")


def _clean_row(row: dict) -> dict:
    """Replace NaN/inf with None so psycopg2 can handle it."""
    out = {}
    for k, v in row.items():
        if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
            out[k] = None
        elif isinstance(v, (np.integer,)):
            out[k] = int(v)
        elif isinstance(v, (np.floating,)):
            out[k] = float(v)
        else:
            out[k] = v
    return out


def load_fact_table(engine, text, csv_name: str, table: str, col_map: dict,
                    unique_cols: list):
    """Generic fact table loader with upsert."""
    df = pd.read_csv(os.path.join(CLEAN_DIR, csv_name))

    # Rename columns per mapping
    df = df.rename(columns=col_map)

    # Only keep columns that exist in table
    keep = [c for c in col_map.values() if c in df.columns]
    df = df[keep].drop_duplicates(subset=unique_cols, keep="first")

    # Build upsert SQL
    cols = list(df.columns)
    placeholders = ", ".join([f":{c}" for c in cols])
    set_clause = ", ".join([f"{c} = EXCLUDED.{c}" for c in cols if c not in unique_cols])
    conflict_cols = ", ".join(unique_cols)

    sql = f"""
        INSERT INTO {table} ({", ".join(cols)})
        VALUES ({placeholders})
        ON CONFLICT ({conflict_cols}) DO UPDATE SET {set_clause}
    """

    rows = [_clean_row(r) for r in df.to_dict("records")]
    with engine.begin() as conn:
        for r in rows:
            try:
                conn.execute(text(sql), r)
            except Exception:
                pass  # Skip rows with FK violations (company not in dim_company)

    print(f"  ✓  {table}: {len(rows)} rows attempted")


def run_data_quality_checks(engine, text):
    """8 checks. Print result for each."""
    print("\n  DATA QUALITY CHECKS:")
    checks = [
        ("Companies loaded",         "SELECT COUNT(*) FROM dim_company",                       92),
        ("Balance sheet rows",       "SELECT COUNT(*) FROM fact_balance_sheet",                1200),
        ("P&L rows",                 "SELECT COUNT(*) FROM fact_profit_loss",                  1200),
        ("Cash flow rows",           "SELECT COUNT(*) FROM fact_cash_flow",                    1100),
        ("No null sales in P&L",     "SELECT COUNT(*) FROM fact_profit_loss WHERE sales IS NULL", 0),
        ("Sectors loaded",           "SELECT COUNT(*) FROM dim_sector",                        1),
        ("Health labels loaded",     "SELECT COUNT(*) FROM dim_health_label",                  5),
        ("Year labels loaded",       "SELECT COUNT(*) FROM dim_year",                          1),
    ]
    all_pass = True
    for label, sql, min_expected in checks:
        try:
            with engine.connect() as conn:
                result = conn.execute(text(sql)).scalar()
            if min_expected == 0:
                ok = result == 0
            else:
                ok = result >= min_expected
            status = "✓" if ok else "✗"
            if not ok:
                all_pass = False
            print(f"    {status}  {label}: {result} (expected {'=' if min_expected==0 else '>='} {min_expected})")
        except Exception as e:
            print(f"    ✗  {label}: ERROR - {e}")
            all_pass = False

    return all_pass


def main():
    print("=" * 60)
    print("STEP 3 — LOAD TO POSTGRESQL DATA WAREHOUSE")
    print(f"  DB: {DB_URL.split('@')[-1] if '@' in DB_URL else DB_URL}")
    print("=" * 60)

    try:
        engine, text = get_engine()
        engine.connect()
        print("  ✓  Database connection established.\n")
    except Exception as e:
        print(f"\n✗  Cannot connect to PostgreSQL: {e}")
        print("\nTo set up PostgreSQL:")
        print("  1. Install PostgreSQL: https://www.postgresql.org/download/")
        print("  2. Create database:  CREATE DATABASE bluestock_dw;")
        print("  3. Set DATABASE_URL in your .env file")
        print("\nThis script requires a running PostgreSQL instance.")
        print("The schema SQL is already saved for when you're ready.")

        # Save schema SQL for reference
        schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "schema.sql")
        os.makedirs(os.path.dirname(schema_path), exist_ok=True)
        with open(schema_path, "w") as f:
            f.write(SCHEMA_SQL)
        print(f"\n  Schema SQL saved to: {schema_path}")
        sys.exit(0)

    # Step 1: Create schema
    print("Creating schema:")
    create_schema(engine, text)

    # Step 2: Load dimension tables first (FK prerequisites)
    print("\nLoading dimension tables:")
    load_dim_sectors(engine, text)
    load_dim_health_labels(engine, text)
    load_dim_companies(engine, text)
    load_dim_years(engine, text)

    # Step 3: Load fact tables
    print("\nLoading fact tables:")

    load_fact_table(engine, text, "profitandloss.csv", "fact_profit_loss",
        col_map={
            "company_id": "symbol", "year": "year_label",
            "sales": "sales", "expenses": "expenses",
            "operating_profit": "operating_profit", "opm_percentage": "opm_pct",
            "other_income": "other_income", "interest": "interest",
            "depreciation": "depreciation", "profit_before_tax": "profit_before_tax",
            "tax_percentage": "tax_pct", "net_profit": "net_profit",
            "eps": "eps", "dividend_payout": "dividend_payout_pct",
            "net_profit_margin_pct": "net_profit_margin_pct",
            "expense_ratio_pct": "expense_ratio_pct",
            "interest_coverage": "interest_coverage",
            "asset_turnover": "asset_turnover",
            "return_on_assets": "return_on_assets",
            "sort_order": "sort_order",
        },
        unique_cols=["symbol", "year_label"]
    )

    load_fact_table(engine, text, "balancesheet.csv", "fact_balance_sheet",
        col_map={
            "company_id": "symbol", "year": "year_label",
            "equity_capital": "equity_capital", "reserves": "reserves",
            "borrowings": "borrowings", "other_liabilities": "other_liabilities",
            "total_liabilities": "total_liabilities", "fixed_assets": "fixed_assets",
            "cwip": "cwip", "investments": "investments",
            "other_asset": "other_asset", "total_assets": "total_assets",
            "debt_to_equity": "debt_to_equity", "equity_ratio": "equity_ratio",
            "sort_order": "sort_order",
        },
        unique_cols=["symbol", "year_label"]
    )

    load_fact_table(engine, text, "cashflow.csv", "fact_cash_flow",
        col_map={
            "company_id": "symbol", "year": "year_label",
            "operating_activity": "operating_activity",
            "investing_activity": "investing_activity",
            "financing_activity": "financing_activity",
            "net_cash_flow": "net_cash_flow",
            "free_cash_flow": "free_cash_flow",
            "cash_conversion_ratio": "cash_conversion_ratio",
            "sort_order": "sort_order",
        },
        unique_cols=["symbol", "year_label"]
    )

    load_fact_table(engine, text, "analysis.csv", "fact_analysis",
        col_map={
            "company_id": "symbol", "metric": "metric",
            "period": "period", "value_pct": "value_pct",
        },
        unique_cols=["symbol", "metric", "period"]
    )

    load_fact_table(engine, text, "documents.csv", "fact_documents",
        col_map={
            "company_id": "symbol", "year": "year",
            "annual_report_url": "annual_report_url",
        },
        unique_cols=["symbol", "year"]
    )

    load_fact_table(engine, text, "prosandcons.csv", "fact_pros_cons",
        col_map={
            "company_id": "symbol", "is_pro": "is_pro",
            "text": "text", "source": "source",
        },
        unique_cols=[]  # No unique constraint — allow multiple entries
    )

    # Step 4: Run quality checks
    print("\nRunning data quality checks:")
    all_pass = run_data_quality_checks(engine, text)

    print("\n" + "=" * 60)
    if all_pass:
        print("✓  Load complete. All quality checks passed.")
    else:
        print("⚠  Load complete with some quality check warnings.")
        print("   Review the ✗ items above and investigate.")


if __name__ == "__main__":
    main()
