"""
ETL Script 1 — Extract
======================
Reads all 7 source Excel files (which represent the MariaDB export)
and saves them as clean CSV files in data/raw/.

Run:  python etl/01_extract_from_excel.py
"""

import os
import sys
import pandas as pd

# ── paths ──────────────────────────────────────────────────────────────────
# Where your uploaded Excel files are
SOURCE_DIR = "/mnt/user-data/uploads"

# Where we save raw CSVs
RAW_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw")
os.makedirs(RAW_DIR, exist_ok=True)

# ── file map ───────────────────────────────────────────────────────────────
# Each entry: (excel_filename, output_csv_name, header_row)
# header_row=1 because each file has a title banner in row 0,
# and the real column names are in row 1.
FILE_MAP = [
    ("companies.xlsx",      "companies.csv",      1),
    ("balancesheet.xlsx",   "balancesheet.csv",   1),
    ("profitandloss.xlsx",  "profitandloss.csv",  1),
    ("cashflow.xlsx",       "cashflow.csv",       1),
    ("analysis__1_.xlsx",   "analysis.csv",       1),
    ("prosandcons.xlsx",    "prosandcons.csv",     1),
    ("documents.xlsx",      "documents.csv",      1),
]


def extract_table(excel_file: str, output_csv: str, header_row: int) -> pd.DataFrame:
    """Read one Excel file and save to CSV. Returns the DataFrame."""
    src_path = os.path.join(SOURCE_DIR, excel_file)
    dst_path = os.path.join(RAW_DIR, output_csv)

    if not os.path.exists(src_path):
        print(f"  ✗  File not found: {src_path}")
        return None

    df = pd.read_excel(src_path, engine="openpyxl", header=header_row)

    # Drop completely empty rows/columns
    df = df.dropna(how="all")
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]  # drop leftover unnamed cols if any

    df.to_csv(dst_path, index=False)
    return df


def main():
    print("=" * 60)
    print("STEP 1 — EXTRACT: Reading source Excel files")
    print("=" * 60)

    results = {}
    all_ok = True

    for excel_file, output_csv, header_row in FILE_MAP:
        table_name = output_csv.replace(".csv", "")
        print(f"\n  ► {excel_file}")
        df = extract_table(excel_file, output_csv, header_row)

        if df is None:
            all_ok = False
            continue

        print(f"    Rows    : {len(df):,}")
        print(f"    Columns : {list(df.columns)}")

        if "company_id" in df.columns:
            print(f"    Companies: {df['company_id'].nunique()}")

        results[table_name] = df

    print("\n" + "=" * 60)
    if all_ok:
        print("✓  All tables extracted successfully.")
        print(f"   Raw CSVs saved to: {RAW_DIR}")
    else:
        print("✗  Some files were missing. Check paths above.")
        sys.exit(1)

    # Quick cross-check
    print("\nRow count summary:")
    for table, df in results.items():
        print(f"  {table:<20} {len(df):>6} rows")

    return results


if __name__ == "__main__":
    main()
