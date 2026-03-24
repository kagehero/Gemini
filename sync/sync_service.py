"""
Incremental sync service.

Uses Microsoft Graph API delta queries so only changed/new/deleted
files are processed on each run — not the full 650GB every time.
"""

import logging
import uuid
from pathlib import Path

from config import settings
from sharepoint import graph_client as gc
from sharepoint.crawler import FileRecord, _is_supported
from sharepoint.downloader import download_files, invalidate_cache, _local_path
from processing.file_parser import parse_file
from processing.chunker import split_text
from processing.cleaner import clean
from embedding.embedder import embed_texts
from vector_db.vectordb import add_chunks, delete_chunks, ChunkDoc
from storage.metadata_store import (
    init_db,
    upsert_file,
    delete_file,
    get_delta_token,
    save_delta_token,
    save_chunk_ids,
    get_chunk_ids,
    needs_reindex,
)

logger = logging.getLogger(__name__)


def _index_file(record: FileRecord, local_path: Path) -> int:
    """Parse → chunk → embed → store one file. Returns chunk count."""
    raw_text = parse_file(local_path)
    clean_text = clean(raw_text)

    if not clean_text.strip():
        logger.debug("Empty content after parsing: %s", record.name)
        return 0

    chunks = split_text(clean_text, source_name=record.name)
    if not chunks:
        return 0

    texts = [c.text for c in chunks]
    embeddings = embed_texts(texts, task_type="RETRIEVAL_DOCUMENT")

    chunk_docs: list[ChunkDoc] = []
    chunk_ids: list[str] = []

    for chunk, embedding in zip(chunks, embeddings):
        cid = str(uuid.uuid4())
        chunk_ids.append(cid)
        chunk_docs.append(
            ChunkDoc(
                chunk_id=cid,
                text=chunk.text,
                embedding=embedding,
                metadata={
                    "item_id": record.item_id,
                    "drive_id": record.drive_id,
                    "site_id": record.site_id,
                    "site_name": record.site_name,
                    "name": record.name,
                    "path": record.path,
                    "extension": record.extension,
                    "last_modified": record.last_modified,
                    "chunk_index": chunk.index,
                },
            )
        )

    # indexed_files に先に行を作る（file_chunks の FOREIGN KEY 用）
    upsert_file(
        item_id=record.item_id,
        drive_id=record.drive_id,
        site_id=record.site_id,
        site_name=record.site_name,
        name=record.name,
        path=record.path,
        extension=record.extension,
        size_bytes=record.size_bytes,
        last_modified=record.last_modified,
        chunk_count=0,
    )

    add_chunks(record.site_name, chunk_docs)
    save_chunk_ids(record.item_id, chunk_ids)
    return len(chunk_docs)


def full_index_site(site_name: str) -> dict:
    """Full initial indexing for a single SharePoint site."""
    from sharepoint.crawler import crawl_site

    init_db()
    logger.info("Full index started: %s", site_name)

    records = crawl_site(site_name)
    logger.info("Files to index: %d", len(records))

    downloaded = download_files(records)
    indexed = 0
    failed = 0

    for record, local_path in downloaded:
        try:
            chunk_count = _index_file(record, local_path)
            upsert_file(
                item_id=record.item_id,
                drive_id=record.drive_id,
                site_id=record.site_id,
                site_name=record.site_name,
                name=record.name,
                path=record.path,
                extension=record.extension,
                size_bytes=record.size_bytes,
                last_modified=record.last_modified,
                chunk_count=chunk_count,
            )
            indexed += 1
        except Exception as exc:
            logger.warning("Indexing failed for %s: %s", record.name, exc)
            failed += 1

    result = {"site": site_name, "indexed": indexed, "failed": failed}
    logger.info("Full index complete: %s", result)
    return result


def delta_sync_drive(drive_id: str, site_id: str, site_name: str) -> dict:
    """
    Fetch only changed files since the last sync using Graph API delta.
    New/modified files are re-indexed; deleted files are removed.
    """
    init_db()
    token = get_delta_token(drive_id)
    logger.info("Delta sync – drive %s (token: %s)", drive_id, "fresh" if not token else "incremental")

    items, new_token = gc.get_delta(drive_id, delta_token=token)

    added = modified = deleted = 0

    processable: list[tuple[dict, FileRecord]] = []
    to_delete: list[str] = []

    for item in items:
        if item.get("deleted"):
            to_delete.append(item["id"])
            continue

        if not _is_supported(item):
            continue

        from pathlib import PurePosixPath
        record = FileRecord(
            item_id=item["id"],
            drive_id=drive_id,
            site_id=site_id,
            site_name=site_name,
            name=item["name"],
            path=item.get("parentReference", {}).get("path", "") + "/" + item["name"],
            extension=PurePosixPath(item["name"]).suffix.lower(),
            size_bytes=item.get("size", 0),
            last_modified=item.get("lastModifiedDateTime", ""),
        )

        if needs_reindex(record.item_id, record.last_modified):
            processable.append((item, record))

    # Remove deleted files
    for item_id in to_delete:
        old_chunks = get_chunk_ids(item_id)
        delete_chunks(site_name, old_chunks)
        delete_file(item_id)
        deleted += 1

    # Download and index changed files
    if processable:
        records_only = [r for _, r in processable]
        downloaded_map = {r.item_id: p for r, p in download_files(records_only)}

        for _, record in processable:
            local_path = downloaded_map.get(record.item_id)
            if not local_path:
                continue
            # Remove old chunks before re-indexing
            old_chunks = get_chunk_ids(record.item_id)
            if old_chunks:
                delete_chunks(site_name, old_chunks)
                modified += 1
            else:
                added += 1
            try:
                chunk_count = _index_file(record, local_path)
                upsert_file(
                    item_id=record.item_id,
                    drive_id=record.drive_id,
                    site_id=record.site_id,
                    site_name=record.site_name,
                    name=record.name,
                    path=record.path,
                    extension=record.extension,
                    size_bytes=record.size_bytes,
                    last_modified=record.last_modified,
                    chunk_count=chunk_count,
                )
                # Evict stale cache so next delta re-downloads if needed
                invalidate_cache(record)
            except Exception as exc:
                logger.warning("Delta index failed for %s: %s", record.name, exc)

    if new_token:
        save_delta_token(drive_id, new_token)

    return {"drive_id": drive_id, "added": added, "modified": modified, "deleted": deleted}


def delta_sync_site(site_name: str) -> list[dict]:
    """Run delta sync for all drives in a site."""
    site = gc.get_site(site_name)
    if not site:
        logger.error("Site not found: %s", site_name)
        return []

    site_id = site["id"]
    drives = gc.list_drives(site_id)
    results = []

    for drive in drives:
        result = delta_sync_drive(drive["id"], site_id, site_name)
        results.append(result)
        logger.info("Drive sync result: %s", result)

    return results


def delta_sync_all() -> list[dict]:
    """Run delta sync for all configured sites."""
    target = settings.TARGET_SITES or []
    if not target:
        logger.warning("No TARGET_SITES configured – nothing to sync")
        return []

    all_results: list[dict] = []
    for site_name in target:
        all_results.extend(delta_sync_site(site_name))
    return all_results
