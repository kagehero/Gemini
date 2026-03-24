"""
Gemini embedding service with batch processing.
Uses the google-genai SDK (v1.x+).
"""

import logging
import time
from typing import Sequence

from google import genai
from google.genai import types

from config import settings

logger = logging.getLogger(__name__)

_EMBED_DIMENSION = settings.EMBED_DIMENSION
_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def embed_texts(texts: Sequence[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """
    Embed a sequence of texts in batches.
    task_type: 'RETRIEVAL_DOCUMENT' for indexing, 'RETRIEVAL_QUERY' for queries.
    """
    if not texts:
        return []

    client = _get_client()
    all_embeddings: list[list[float]] = []
    batch_size = settings.BATCH_SIZE

    for i in range(0, len(texts), batch_size):
        batch = list(texts[i : i + batch_size])
        success = False
        for attempt in range(5):
            try:
                result = client.models.embed_content(
                    model=settings.GEMINI_EMBED_MODEL,
                    contents=batch,
                    config=types.EmbedContentConfig(task_type=task_type),
                )
                for embedding in result.embeddings:
                    all_embeddings.append(embedding.values)
                success = True
                break
            except Exception as exc:
                wait = 2 ** attempt
                logger.warning(
                    "Embedding attempt %d failed: %s – retrying in %ds",
                    attempt + 1, exc, wait,
                )
                time.sleep(wait)

        if not success:
            logger.error("Embedding failed after retries for batch at index %d", i)
            all_embeddings.extend([[0.0] * _EMBED_DIMENSION for _ in batch])

    return all_embeddings


def embed_query(query: str) -> list[float]:
    """Embed a single query string."""
    results = embed_texts([query], task_type="RETRIEVAL_QUERY")
    return results[0] if results else [0.0] * _EMBED_DIMENSION
