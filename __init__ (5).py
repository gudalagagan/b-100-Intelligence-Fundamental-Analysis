#!/usr/bin/env python3
"""
Bluestock Fintech — One-click launcher
Run: python run.py
Then open: http://localhost:8000
"""
import os, sys, subprocess

os.chdir(os.path.dirname(os.path.abspath(__file__)))

print("=" * 55)
print("  BLUESTOCK FINTECH — B100 Intelligence Platform")
print("=" * 55)
print()

# Check Python deps
missing = []
for pkg in ["django","pandas","numpy","openpyxl"]:
    try: __import__(pkg)
    except ImportError: missing.append(pkg)

if missing:
    print(f"Installing: {', '.join(missing)}")
    subprocess.run([sys.executable,"-m","pip","install",*missing,"--break-system-packages","-q"])

# Migrate
subprocess.run([sys.executable,"manage.py","migrate","--run-syncdb","-v","0"])

print()
print("  ✓  Server starting at http://localhost:8000")
print("  ✓  Press Ctrl+C to stop")
print()
print("  Pages:")
print("    http://localhost:8000/           → Home")
print("    http://localhost:8000/companies/ → All 100 Companies")
print("    http://localhost:8000/screener/  → Financial Screener")
print("    http://localhost:8000/compare/   → Compare Companies")
print()

subprocess.run([sys.executable,"manage.py","runserver","8000"])
