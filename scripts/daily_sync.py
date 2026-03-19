"""
Daily sync script — run this once per day (via cron or scheduler).

Usage:
  # Run sync once immediately
  python -m scripts.daily_sync --now

  # Start scheduler daemon (runs at SYNC_TIME every day)
  python -m scripts.daily_sync --daemon

Cron example (2 AM daily):
  0 2 * * * /path/to/venv/bin/python -m scripts.daily_sync --now
"""

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("daily_sync")


def run_sync():
    from config import settings
    from storage.metadata_store import init_db, get_stats
    from sync.sync_service import delta_sync_all

    init_db()
    logger.info("Daily sync started")
    results = delta_sync_all()

    total_added = sum(r.get("added", 0) for r in results)
    total_modified = sum(r.get("modified", 0) for r in results)
    total_deleted = sum(r.get("deleted", 0) for r in results)

    logger.info(
        "Sync complete – added: %d, modified: %d, deleted: %d",
        total_added, total_modified, total_deleted,
    )

    stats = get_stats()
    logger.info(
        "Index stats – files: %d, chunks: %d",
        stats["total_files"], stats["total_chunks"],
    )
    return results


def main():
    parser = argparse.ArgumentParser(description="Daily SharePoint sync")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--now", action="store_true", help="Run sync immediately and exit")
    group.add_argument("--daemon", action="store_true", help="Run as scheduler daemon")
    args = parser.parse_args()

    if args.now:
        run_sync()
        return

    # Daemon mode
    import schedule
    from config import settings

    sync_time = settings.SYNC_TIME
    logger.info("Scheduler started – sync will run daily at %s", sync_time)

    schedule.every().day.at(sync_time).do(run_sync)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
