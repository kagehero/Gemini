"""
Initial indexing script.

Usage:
  python -m scripts.initial_index                  # index PILOT_SITE
  python -m scripts.initial_index --site TCS事業   # index specific site
  python -m scripts.initial_index --all            # index all TARGET_SITES
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("initial_index")


def main():
    parser = argparse.ArgumentParser(description="SharePoint initial indexer")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--site", type=str, help="Site name to index")
    group.add_argument("--all", action="store_true", help="Index all TARGET_SITES")
    args = parser.parse_args()

    from config import settings
    from storage.metadata_store import init_db, get_stats
    from sync.sync_service import full_index_site

    init_db()

    if args.all:
        sites = settings.TARGET_SITES
        if not sites:
            logger.error("TARGET_SITES is empty. Set it in .env")
            sys.exit(1)
    elif args.site:
        sites = [args.site]
    else:
        site = settings.PILOT_SITE
        if not site:
            logger.error("No --site specified and PILOT_SITE is not set in .env")
            sys.exit(1)
        sites = [site]

    logger.info("Starting initial index for: %s", sites)

    for site_name in sites:
        result = full_index_site(site_name)
        logger.info("Result: %s", result)

    stats = get_stats()
    print("\n── Index Statistics ──────────────────────────────────")
    print(f"  Total files : {stats['total_files']}")
    print(f"  Total chunks: {stats['total_chunks']}")
    for site, count in stats["by_site"].items():
        print(f"    {site}: {count} files")
    print("──────────────────────────────────────────────────────\n")


if __name__ == "__main__":
    main()
