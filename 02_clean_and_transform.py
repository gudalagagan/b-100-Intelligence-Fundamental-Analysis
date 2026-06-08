-- ============================================================
-- Bluestock Fintech — PostgreSQL Star Schema
-- Run this ONCE to create the data warehouse structure
-- Usage: psql -U postgres -d bluestock_dw -f schema.sql
-- ============================================================

-- Create database (run as superuser if needed)
-- CREATE DATABASE bluestock_dw;

-- ── DIMENSION TABLES ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS dim_sector (
    sector_id   SERIAL PRIMARY KEY,
    sector_name VARCHAR(100) UNIQUE NOT NULL,
    sector_code VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS dim_health_label (
    label_id   SERIAL PRIMARY KEY,
    label_name VARCHAR(20) UNIQUE NOT NULL,
    min_score  NUMERIC(5,2) NOT NULL,
    max_score  NUMERIC(5,2) NOT NULL,
    color_hex  VARCHAR(7)   NOT NULL
);

-- Seed health labels
INSERT INTO dim_health_label (label_name, min_score, max_score, color_hex) VALUES
    ('EXCELLENT', 85.0, 100.0, '#2ECC71'),
    ('GOOD',      70.0,  84.9, '#27AE60'),
    ('AVERAGE',   50.0,  69.9, '#F39C12'),
    ('WEAK',      35.0,  49.9, '#E67E22'),
    ('POOR',       0.0,  34.9, '#E74C3C')
ON CONFLICT (label_name) DO NOTHING;

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

-- ── FACT TABLES ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS fact_profit_loss (
    id                    SERIAL PRIMARY KEY,
    symbol                VARCHAR(30) REFERENCES dim_company(symbol),
    year_label            VARCHAR(20),
    sales                 NUMERIC(20,2),
    expenses              NUMERIC(20,2),
    operating_profit      NUMERIC(20,2),
    opm_pct               NUMERIC(10,4),
    other_income          NUMERIC(20,2),
    interest              NUMERIC(20,2),
    depreciation          NUMERIC(20,2),
    profit_before_tax     NUMERIC(20,2),
    tax_pct               NUMERIC(10,4),
    net_profit            NUMERIC(20,2),
    eps                   NUMERIC(15,4),
    dividend_payout_pct   NUMERIC(10,4),
    net_profit_margin_pct NUMERIC(10,4),
    expense_ratio_pct     NUMERIC(10,4),
    interest_coverage     NUMERIC(15,4),
    asset_turnover        NUMERIC(15,6),
    return_on_assets      NUMERIC(10,4),
    sort_order            INTEGER,
    UNIQUE (symbol, year_label)
);

CREATE TABLE IF NOT EXISTS fact_balance_sheet (
    id                SERIAL PRIMARY KEY,
    symbol            VARCHAR(30) REFERENCES dim_company(symbol),
    year_label        VARCHAR(20),
    equity_capital    NUMERIC(20,2),
    reserves          NUMERIC(20,2),
    borrowings        NUMERIC(20,2),
    other_liabilities NUMERIC(20,2),
    total_liabilities NUMERIC(20,2),
    fixed_assets      NUMERIC(20,2),
    cwip              NUMERIC(20,2),
    investments       NUMERIC(20,2),
    other_asset       NUMERIC(20,2),
    total_assets      NUMERIC(20,2),
    debt_to_equity    NUMERIC(15,6),
    equity_ratio      NUMERIC(15,6),
    sort_order        INTEGER,
    UNIQUE (symbol, year_label)
);

CREATE TABLE IF NOT EXISTS fact_cash_flow (
    id                    SERIAL PRIMARY KEY,
    symbol                VARCHAR(30) REFERENCES dim_company(symbol),
    year_label            VARCHAR(20),
    operating_activity    NUMERIC(20,2),
    investing_activity    NUMERIC(20,2),
    financing_activity    NUMERIC(20,2),
    net_cash_flow         NUMERIC(20,2),
    free_cash_flow        NUMERIC(20,2),
    cash_conversion_ratio NUMERIC(15,6),
    sort_order            INTEGER,
    UNIQUE (symbol, year_label)
);

CREATE TABLE IF NOT EXISTS fact_analysis (
    id         SERIAL PRIMARY KEY,
    symbol     VARCHAR(30) REFERENCES dim_company(symbol),
    metric     VARCHAR(60),
    period     VARCHAR(10),
    value_pct  NUMERIC(10,4),
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
    id           SERIAL PRIMARY KEY,
    symbol       VARCHAR(30) REFERENCES dim_company(symbol),
    is_pro       BOOLEAN,
    text         TEXT,
    source       VARCHAR(20) DEFAULT 'MANUAL',
    confidence   NUMERIC(5,4),
    generated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fact_documents (
    id                SERIAL PRIMARY KEY,
    symbol            VARCHAR(30) REFERENCES dim_company(symbol),
    year              INTEGER,
    annual_report_url TEXT,
    UNIQUE (symbol, year)
);

-- ── INDEXES ──────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_pl_symbol   ON fact_profit_loss(symbol);
CREATE INDEX IF NOT EXISTS idx_pl_year     ON fact_profit_loss(year_label);
CREATE INDEX IF NOT EXISTS idx_bs_symbol   ON fact_balance_sheet(symbol);
CREATE INDEX IF NOT EXISTS idx_bs_year     ON fact_balance_sheet(year_label);
CREATE INDEX IF NOT EXISTS idx_cf_symbol   ON fact_cash_flow(symbol);
CREATE INDEX IF NOT EXISTS idx_cf_year     ON fact_cash_flow(year_label);
CREATE INDEX IF NOT EXISTS idx_scores_sym  ON fact_ml_scores(symbol);
CREATE INDEX IF NOT EXISTS idx_scores_time ON fact_ml_scores(computed_at);

-- Done
SELECT 'Schema created successfully.' AS status;
