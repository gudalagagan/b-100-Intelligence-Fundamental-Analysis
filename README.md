# Bluestock Fintech — B100 Financial Intelligence Platform

## Quick Start (3 steps)

```bash
# 1. Make sure Python 3.9+ is installed
python --version

# 2. Install dependencies
pip install django pandas numpy openpyxl

# 3. Run the app
cd django_app
python run.py
```

Then open **http://localhost:8000** in your browser.

---

## What's Inside

| Page | URL | What it does |
|------|-----|-------------|
| Home | `/` | Search, featured companies, sector cards |
| Companies | `/companies/` | All 92 companies, filter by sector/health |
| Company Detail | `/company/TCS/` | 8 live Chart.js charts, pros/cons, annual reports |
| Screener | `/screener/` | Filter by OPM%, D/E ratio, health score |
| Compare | `/compare/` | Side-by-side comparison of 2-4 companies |
| Sector | `/sector/IT/` | All companies in a sector |
| API | `/api/charts/TCS/` | JSON data endpoint |

## Try These URLs First

- http://localhost:8000/company/TCS/
- http://localhost:8000/company/HDFCBANK/
- http://localhost:8000/company/ADANIPOWER/
- http://localhost:8000/screener/?label=EXCELLENT
- http://localhost:8000/compare/?s=TCS&s=INFY&s=WIPRO
- http://localhost:8000/sector/Banking/

## Project Structure

```
bluestock_fintech/
├── data/
│   ├── raw/          ← Extracted CSVs from Excel
│   └── clean/        ← Cleaned & computed CSVs (used by web app)
├── etl/
│   ├── 01_extract_from_excel.py
│   ├── 02_clean_and_transform.py
│   └── 03_load_to_warehouse.py   ← Run when PostgreSQL is ready
├── django_app/
│   ├── run.py        ← ONE-CLICK LAUNCHER
│   ├── data/         ← Clean CSVs (copied here for the web app)
│   ├── companies/    ← Django app: views, data_service
│   └── templates/    ← All HTML pages
├── notebooks/        ← Jupyter notebooks (Week 2-5 work)
└── README.md
```

## For the Demo

1. Run `python run.py` from the `django_app/` folder
2. Open http://localhost:8000
3. Click any company → shows 8 live financial charts
4. Use the screener to filter companies
5. Compare TCS vs INFY vs WIPRO side by side

---
*Bluestock Fintech | Intern Project | Educational use only | Not financial advice*
