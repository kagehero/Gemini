"""
Parallel file downloader using ThreadPoolExecutor.
Downloads are cached on disk; already-cached files are skipped.
"""

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tqdm import tqdm

from config import settings
from sharepoint import graph_client as gc
from sharepoint.crawler import FileRecord

logger = logging.getLogger(__name__)


def _local_path(record: FileRecord) -> Path:
    """Deterministic local cache path for a record."""
    safe_name = hashlib.md5(record.item_id.encode()).hexdigest()[:12]
    ext = record.extension
    site_dir = settings.DOWNLOAD_DIR / record.site_name.replace("/", "_")
    site_dir.mkdir(parents=True, exist_ok=True)
    return site_dir / f"{safe_name}{ext}"


def _download_one(record: FileRecord) -> tuple[FileRecord, Path | None]:
    local = _local_path(record)

    if local.exists():
        return record, local

    try:
        data = gc.download_item(record.drive_id, record.item_id)
        local.write_bytes(data)
        return record, local
    except Exception as exc:
        logger.warning("Failed to download %s: %s", record.name, exc)
        return record, None


def download_files(
    records: list[FileRecord],
    workers: int | None = None,
) -> list[tuple[FileRecord, Path]]:
    """
    Download all records in parallel.
    Returns list of (record, local_path) for successfully downloaded files.
    """
    n_workers = workers or settings.MAX_WORKERS
    results: list[tuple[FileRecord, Path]] = []

    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        futures = {pool.submit(_download_one, r): r for r in records}
        for future in tqdm(as_completed(futures), total=len(futures), desc="Downloading"):
            record, path = future.result()
            if path:
                results.append((record, path))

    logger.info("Downloaded %d / %d files", len(results), len(records))
    return results


def invalidate_cache(record: FileRecord) -> None:
    """Remove cached file so it will be re-downloaded on next run."""
    path = _local_path(record)
    if path.exists():
        path.unlink()
