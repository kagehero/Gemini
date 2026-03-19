"""
Recursively crawl SharePoint sites and build a flat list of file metadata.
Only supported file types within the size limit are included.
"""

import logging
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from config import settings
from sharepoint import graph_client as gc

logger = logging.getLogger(__name__)


@dataclass
class FileRecord:
    item_id: str
    drive_id: str
    site_id: str
    site_name: str
    name: str
    path: str
    extension: str
    size_bytes: int
    last_modified: str


def _is_supported(item: dict) -> bool:
    """True if the item is a processable file (not a folder)."""
    if "folder" in item:
        return False
    if "file" not in item:
        return False

    name = item.get("name", "")
    ext = PurePosixPath(name).suffix.lower()
    size = item.get("size", 0)

    return (
        ext in settings.SUPPORTED_EXTENSIONS
        and 0 < size <= settings.MAX_FILE_SIZE_BYTES
    )


def _crawl_folder(drive_id: str, folder_id: str, site_id: str, site_name: str) -> list[FileRecord]:
    records: list[FileRecord] = []

    try:
        children = gc.list_children(drive_id, folder_id)
    except Exception as exc:
        logger.warning("Cannot read folder %s: %s", folder_id, exc)
        return records

    for item in children:
        if "folder" in item:
            records.extend(_crawl_folder(drive_id, item["id"], site_id, site_name))
        elif _is_supported(item):
            parent_path = item.get("parentReference", {}).get("path", "")
            records.append(
                FileRecord(
                    item_id=item["id"],
                    drive_id=drive_id,
                    site_id=site_id,
                    site_name=site_name,
                    name=item["name"],
                    path=f"{parent_path}/{item['name']}",
                    extension=PurePosixPath(item["name"]).suffix.lower(),
                    size_bytes=item.get("size", 0),
                    last_modified=item.get("lastModifiedDateTime", ""),
                )
            )

    return records


def crawl_site(site_name: str) -> list[FileRecord]:
    """Return all supported files in the given SharePoint site."""
    logger.info("Crawling site: %s", site_name)

    site = gc.get_site(site_name)
    if not site:
        logger.error("Site not found: %s", site_name)
        return []

    site_id = site["id"]
    drives = gc.list_drives(site_id)
    all_records: list[FileRecord] = []

    for drive in drives:
        drive_id = drive["id"]
        drive_name = drive.get("name", drive_id)
        logger.info("  Drive: %s (%s)", drive_name, drive_id)
        records = _crawl_folder(drive_id, "root", site_id, site_name)
        logger.info("  → %d supported files", len(records))
        all_records.extend(records)

    return all_records


def crawl_all_sites() -> list[FileRecord]:
    """Crawl all configured sites (or all tenant sites if none configured)."""
    target = settings.TARGET_SITES or []

    if not target:
        logger.info("No TARGET_SITES set – crawling all tenant sites")
        sites = gc.list_sites()
        target = [s.get("displayName", "") for s in sites if s.get("displayName")]

    all_records: list[FileRecord] = []
    for site_name in target:
        all_records.extend(crawl_site(site_name))

    logger.info("Total files found: %d", len(all_records))
    return all_records
