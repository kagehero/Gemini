"""
SQLite-backed metadata store.

Tracks:
  - indexed files (item_id, drive_id, site_name, last_modified, chunk_count)
  - delta tokens per drive (for incremental sync)
  - indexed chunk IDs for cleanup on update/delete
"""

import sqlite3
import logging
from contextlib import contextmanager
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)


_CREATE_FILES = """
CREATE TABLE IF NOT EXISTS indexed_files (
    item_id       TEXT PRIMARY KEY,
    drive_id      TEXT NOT NULL,
    site_id       TEXT NOT NULL,
    site_name     TEXT NOT NULL,
    name          TEXT NOT NULL,
    path          TEXT NOT NULL,
    extension     TEXT NOT NULL,
    size_bytes    INTEGER NOT NULL DEFAULT 0,
    last_modified TEXT NOT NULL,
    chunk_count   INTEGER NOT NULL DEFAULT 0,
    indexed_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_CREATE_DELTA = """
CREATE TABLE IF NOT EXISTS delta_tokens (
    drive_id    TEXT PRIMARY KEY,
    token       TEXT NOT NULL,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_CREATE_CHUNKS = """
CREATE TABLE IF NOT EXISTS file_chunks (
    chunk_id  TEXT PRIMARY KEY,
    item_id   TEXT NOT NULL,
    FOREIGN KEY (item_id) REFERENCES indexed_files(item_id) ON DELETE CASCADE
);
"""


@contextmanager
def _conn():
    con = sqlite3.connect(str(settings.METADATA_DB_PATH))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db() -> None:
    with _conn() as con:
        con.execute(_CREATE_FILES)
        con.execute(_CREATE_DELTA)
        con.execute(_CREATE_CHUNKS)
    logger.debug("Metadata DB ready: %s", settings.METADATA_DB_PATH)


# ── Indexed files ─────────────────────────────────────────────

def upsert_file(
    *,
    item_id: str,
    drive_id: str,
    site_id: str,
    site_name: str,
    name: str,
    path: str,
    extension: str,
    size_bytes: int,
    last_modified: str,
    chunk_count: int,
) -> None:
    sql = """
        INSERT INTO indexed_files
            (item_id, drive_id, site_id, site_name, name, path, extension,
             size_bytes, last_modified, chunk_count, indexed_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,datetime('now'))
        ON CONFLICT(item_id) DO UPDATE SET
            last_modified = excluded.last_modified,
            chunk_count   = excluded.chunk_count,
            indexed_at    = datetime('now')
    """
    with _conn() as con:
        con.execute(sql, (item_id, drive_id, site_id, site_name, name,
                          path, extension, size_bytes, last_modified, chunk_count))


def delete_file(item_id: str) -> None:
    with _conn() as con:
        con.execute("DELETE FROM indexed_files WHERE item_id = ?", (item_id,))


def get_file(item_id: str) -> sqlite3.Row | None:
    with _conn() as con:
        return con.execute(
            "SELECT * FROM indexed_files WHERE item_id = ?", (item_id,)
        ).fetchone()


def get_all_files() -> list[sqlite3.Row]:
    with _conn() as con:
        return con.execute("SELECT * FROM indexed_files").fetchall()


def needs_reindex(item_id: str, last_modified: str) -> bool:
    row = get_file(item_id)
    if row is None:
        return True
    return row["last_modified"] != last_modified


# ── Chunk IDs ─────────────────────────────────────────────────

def save_chunk_ids(item_id: str, chunk_ids: list[str]) -> None:
    with _conn() as con:
        con.execute("DELETE FROM file_chunks WHERE item_id = ?", (item_id,))
        con.executemany(
            "INSERT INTO file_chunks (chunk_id, item_id) VALUES (?,?)",
            [(cid, item_id) for cid in chunk_ids],
        )


def get_chunk_ids(item_id: str) -> list[str]:
    with _conn() as con:
        rows = con.execute(
            "SELECT chunk_id FROM file_chunks WHERE item_id = ?", (item_id,)
        ).fetchall()
        return [r["chunk_id"] for r in rows]


# ── Delta tokens ──────────────────────────────────────────────

def save_delta_token(drive_id: str, token: str) -> None:
    with _conn() as con:
        con.execute(
            """INSERT INTO delta_tokens (drive_id, token, updated_at)
               VALUES (?,?,datetime('now'))
               ON CONFLICT(drive_id) DO UPDATE SET
                   token = excluded.token,
                   updated_at = datetime('now')""",
            (drive_id, token),
        )


def get_delta_token(drive_id: str) -> str | None:
    with _conn() as con:
        row = con.execute(
            "SELECT token FROM delta_tokens WHERE drive_id = ?", (drive_id,)
        ).fetchone()
        return row["token"] if row else None


# ── Stats ─────────────────────────────────────────────────────

def get_stats() -> dict:
    with _conn() as con:
        total = con.execute("SELECT COUNT(*) as n FROM indexed_files").fetchone()["n"]
        sites = con.execute(
            "SELECT site_name, COUNT(*) as n FROM indexed_files GROUP BY site_name"
        ).fetchall()
        chunks = con.execute("SELECT SUM(chunk_count) as n FROM indexed_files").fetchone()["n"] or 0
    return {
        "total_files": total,
        "total_chunks": chunks,
        "by_site": {r["site_name"]: r["n"] for r in sites},
    }
