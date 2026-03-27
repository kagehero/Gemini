"""
Scan an Excel file for SharePoint site URLs and print unique site path names.

Useful for building TARGET_SITES from a reference workbook (e.g. 参考1_SharePoint資料.xlsx).

Recognizes URLs like: https://tenant.sharepoint.com/sites/SiteName/...

Usage:
  .venv/bin/python -m scripts.extract_site_names_from_excel [path/to/file.xlsx]

Prints one site name per line; also prints a TARGET_SITES=... line to stderr.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd


def site_name_from_cell(value: object) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if not isinstance(value, str):
        value = str(value)
    u = value.strip()
    if "sharepoint.com" not in u.lower() or "/sites/" not in u.lower():
        return None
    m = re.search(r"/sites/([^/?#]+)", u, re.IGNORECASE)
    if not m:
        return None
    return unquote(m.group(1).rstrip("/"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract SharePoint site names from Excel URLs")
    parser.add_argument(
        "xlsx",
        nargs="?",
        default=str(Path(__file__).parent.parent / "参考1_SharePoint資料.xlsx"),
        help="Path to .xlsx (default: project root 参考1_SharePoint資料.xlsx)",
    )
    args = parser.parse_args()
    path = Path(args.xlsx)
    if not path.is_file():
        print(f"File not found: {path}", file=sys.stderr)
        sys.exit(1)

    found: set[str] = set()
    xl = pd.ExcelFile(path)
    for sheet in xl.sheet_names:
        df = xl.parse(sheet)
        for col in df.columns:
            for v in df[col]:
                s = site_name_from_cell(v)
                if s:
                    found.add(s)

    if not found:
        print("No SharePoint /sites/... URLs found in workbook.", file=sys.stderr)
        sys.exit(1)

    for n in sorted(found):
        print(n)
    print(f"\nTARGET_SITES={','.join(sorted(found))}", file=sys.stderr)


if __name__ == "__main__":
    main()
