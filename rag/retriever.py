"""
Retrieval layer: embed the user's query and fetch relevant chunks.
"""

import logging

from embedding.embedder import embed_query
from vector_db.vectordb import query_collection
from config import settings

logger = logging.getLogger(__name__)


def retrieve(
    query: str,
    site_name: str | None = None,
    top_k: int | None = None,
    min_score: float = 0.75,
) -> list[dict]:
    """
    Embed the query and return top-k relevant document chunks.

    Parameters
    ----------
    query     : natural language question
    site_name : restrict search to a specific SharePoint site (None = global)
    top_k     : number of results (falls back to settings.TOP_K)
    min_score : cosine similarity threshold (0–1). Lower = stricter.
                ChromaDB reports distance so we convert: similarity = 1 - distance

    Returns
    -------
    list of dicts with keys: id, text, metadata, distance, similarity
    """
    k = top_k or settings.TOP_K
    query_vec = embed_query(query)
    raw = query_collection(query_embedding=query_vec, site_name=site_name, top_k=k * 2)

    results = []
    for doc in raw:
        similarity = 1.0 - doc["distance"]
        if similarity < min_score:
            continue
        results.append({**doc, "similarity": round(similarity, 4)})

    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:k]
