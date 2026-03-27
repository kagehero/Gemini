"""
FastAPI — exposes hybrid / RAG query and stats for the Next.js frontend.

Run:
  uvicorn api.app:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Geminni API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.API_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryBody(BaseModel):
    question: str = Field(..., min_length=1, description="ユーザーの質問")
    mode: Literal["hybrid", "rag"] = "hybrid"
    site: str | None = Field(None, description="SharePoint サイト名（例: eco-action）")
    top_k: int | None = Field(None, ge=1, le=50, description="RAG: 取得チャンク数")
    hybrid_top: int | None = Field(None, ge=1, le=20, description="Hybrid: 取得ファイル数上限")


class QueryResponse(BaseModel):
    question: str
    answer: str
    retrieved_count: int
    sources: list[dict[str, Any]]
    mode: str


class StatsResponse(BaseModel):
    total_files: int
    total_chunks: int
    by_site: dict[str, int]
    vector_collections: dict[str, int]


def _answer_to_payload(answer, mode: str) -> QueryResponse:
    return QueryResponse(
        question=answer.question,
        answer=answer.answer,
        retrieved_count=answer.retrieved_count,
        sources=list(answer.sources),
        mode=mode,
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/stats", response_model=StatsResponse)
def stats() -> StatsResponse:
    from storage.metadata_store import init_db, get_stats
    from vector_db.vectordb import get_collection_stats

    init_db()
    meta = get_stats()
    vec = get_collection_stats()
    return StatsResponse(
        total_files=meta["total_files"],
        total_chunks=meta["total_chunks"],
        by_site=meta.get("by_site", {}),
        vector_collections=vec,
    )


@app.post("/api/query", response_model=QueryResponse)
def query(body: QueryBody) -> QueryResponse:
    q = body.question.strip()
    if not q:
        raise HTTPException(status_code=400, detail="question is empty")

    top_k = body.top_k or settings.TOP_K
    hybrid_top = body.hybrid_top or settings.HYBRID_TOP_FILES

    try:
        if body.mode == "hybrid":
            from rag.hybrid_qa import ask_hybrid

            ans = ask_hybrid(q, site_name=body.site, top_files=hybrid_top)
        else:
            from rag.qa_engine import ask

            ans = ask(q, site_name=body.site, top_k=top_k)
    except Exception as exc:
        logger.exception("Query failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return _answer_to_payload(ans, body.mode)


def create_app() -> FastAPI:
    return app
