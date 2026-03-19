"""
ChromaDB vector store wrapper.

Collections are organized per SharePoint site for faster, scoped retrieval.
The global 'all_sites' collection supports cross-site search.
"""

import logging
import uuid
from dataclasses import dataclass

import chromadb
from chromadb.api.client import Client as ChromaClient

from config import settings

logger = logging.getLogger(__name__)

_client: "ChromaClient | None" = None


def _get_client() -> ChromaClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=str(settings.VECTOR_DB_DIR))
    return _client


def _collection_name(site_name: str) -> str:
    """Normalise site name to a valid ChromaDB collection name."""
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in site_name)
    return f"site_{safe}"[:63]


def get_or_create_collection(site_name: str) -> chromadb.Collection:
    client = _get_client()
    name = _collection_name(site_name)
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def get_global_collection() -> chromadb.Collection:
    client = _get_client()
    return client.get_or_create_collection(
        name="all_sites",
        metadata={"hnsw:space": "cosine"},
    )


@dataclass
class ChunkDoc:
    chunk_id: str
    text: str
    embedding: list[float]
    metadata: dict


def add_chunks(
    site_name: str,
    chunks: list[ChunkDoc],
) -> list[str]:
    """
    Add chunk documents to both the site-specific and global collections.
    Returns list of chunk IDs inserted.
    """
    if not chunks:
        return []

    site_col = get_or_create_collection(site_name)
    global_col = get_global_collection()

    ids = [c.chunk_id for c in chunks]
    texts = [c.text for c in chunks]
    embeddings = [c.embedding for c in chunks]
    metadatas = [c.metadata for c in chunks]

    site_col.upsert(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)
    global_col.upsert(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)

    return ids


def delete_chunks(site_name: str, chunk_ids: list[str]) -> None:
    """Remove chunks from both collections (used during re-indexing)."""
    if not chunk_ids:
        return
    try:
        get_or_create_collection(site_name).delete(ids=chunk_ids)
    except Exception as exc:
        logger.debug("Site collection delete: %s", exc)
    try:
        get_global_collection().delete(ids=chunk_ids)
    except Exception as exc:
        logger.debug("Global collection delete: %s", exc)


def query_collection(
    query_embedding: list[float],
    site_name: str | None = None,
    top_k: int | None = None,
    where: dict | None = None,
) -> list[dict]:
    """
    Retrieve the top-k most similar chunks.
    When site_name is None, searches across all sites.
    Returns list of {id, text, metadata, distance}.
    """
    k = top_k or settings.TOP_K
    col = get_or_create_collection(site_name) if site_name else get_global_collection()

    try:
        result = col.query(
            query_embeddings=[query_embedding],
            n_results=min(k, col.count()),
            where=where or None,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as exc:
        logger.error("Vector query failed: %s", exc)
        return []

    docs = []
    for i, doc_id in enumerate(result["ids"][0]):
        docs.append(
            {
                "id": doc_id,
                "text": result["documents"][0][i],
                "metadata": result["metadatas"][0][i],
                "distance": result["distances"][0][i],
            }
        )
    return docs


def get_collection_stats() -> dict:
    client = _get_client()
    stats: dict[str, int] = {}
    for col in client.list_collections():
        try:
            stats[col.name] = col.count()
        except Exception:
            stats[col.name] = -1
    return stats
