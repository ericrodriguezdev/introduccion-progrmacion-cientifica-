#!/usr/bin/env python3
"""Convert an Excel file to a CSV (row-wise)."""
import sys
from pathlib import Path

def main(argv):
    if len(argv) < 3:
        print("Usage: python convert_excel_to_csv.py INPUT.xlsx OUTPUT.csv")
        return 1
    src = Path(argv[1])
    dst = Path(argv[2])
    if not src.exists():
        print(f"Input not found: {src}")
        return 2
    try:
        import pandas as pd
    except Exception:
        print("pandas required: pip install pandas openpyxl")
        return 3

    try:
        xls = pd.read_excel(src, sheet_name=None)
    except Exception as e:
        print(f"Failed to read Excel: {e}")
        return 4

    if isinstance(xls, dict):
        dfs = []
        for name, df in xls.items():
            df = df.copy()
            df.insert(0, '_sheet', name)
            dfs.append(df)
        out = pd.concat(dfs, ignore_index=True)
    else:
        out = xls

    try:
        out.to_csv(dst, index=False)
    except Exception as e:
        print(f"Failed to write CSV: {e}")
        return 5

    print(f"Wrote {dst} ({len(out)} rows)")
    return 0

if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
