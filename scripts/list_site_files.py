"""
List all supported files under a SharePoint site (recursive, all document libraries).

Uses the same crawl as full RAG indexing. Hybrid search does not use this list —
it queries Microsoft Search — but this shows what exists via Graph for a site.

Usage:
  .venv/bin/python -m scripts.list_site_files --site eco-action
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="List crawlable files for a SharePoint site")
    parser.add_argument("--site", required=True, help="Site path name (e.g. eco-action)")
    args = parser.parse_args()

    from sharepoint.crawler import crawl_site

    records = crawl_site(args.site)
    for r in records:
        print(r.path)
    print(f"# total files (supported extensions & size rules): {len(records)}", file=sys.stderr)


if __name__ == "__main__":
    main()
