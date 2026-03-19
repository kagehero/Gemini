"""
Heading-aware text chunker.
Prefers to split at headings / paragraph boundaries for better retrieval accuracy.
"""

import re
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import settings

# Approximate characters per token for Japanese + English mixed text
_CHARS_PER_TOKEN = 2.5

_HEADING_RE = re.compile(r"^(#+\s|\d+[\.．]\s|【.+?】|\[.+?\])", re.MULTILINE)


@dataclass
class Chunk:
    text: str
    index: int        # position in the document
    char_start: int


def _estimate_chunk_size_chars() -> int:
    return int(settings.CHUNK_SIZE * _CHARS_PER_TOKEN)


def _estimate_overlap_chars() -> int:
    return int(settings.CHUNK_OVERLAP * _CHARS_PER_TOKEN)


def split_text(text: str, source_name: str = "") -> list[Chunk]:
    """
    Split text into overlapping chunks that fit within the token budget.
    Returns a list of Chunk objects.
    """
    if not text or not text.strip():
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=_estimate_chunk_size_chars(),
        chunk_overlap=_estimate_overlap_chars(),
        separators=["\n\n", "\n", "。", "．", ".", " ", ""],
        keep_separator=True,
    )

    raw_chunks = splitter.split_text(text)
    chunks: list[Chunk] = []
    cursor = 0

    for i, raw in enumerate(raw_chunks):
        start = text.find(raw, cursor)
        if start == -1:
            start = cursor
        chunks.append(Chunk(text=raw.strip(), index=i, char_start=start))
        cursor = max(cursor, start + len(raw) - _estimate_overlap_chars())

    return [c for c in chunks if len(c.text) > 50]
