"""
QA engine: build a Gemini prompt from retrieved chunks and generate an answer.
Uses the google-genai SDK (v1.x+).
"""

import logging
import time
from dataclasses import dataclass

from google import genai

from config import settings
from rag.retriever import retrieve

logger = logging.getLogger(__name__)

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


_GEMINI_MAX_RETRIES = 5
_GEMINI_BASE_DELAY_S = 2.0


def generate_content_answer(prompt: str) -> str:
    """
    Call Gemini generate_content. Retries with exponential backoff on 429 / quota.
    Returns answer text, or a user-facing error string on failure.
    """
    client = _get_client()
    for attempt in range(_GEMINI_MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
            )
            return (response.text or "").strip()
        except Exception as exc:
            msg = str(exc).lower()
            retriable = "429" in msg or "resource_exhausted" in msg
            if not retriable:
                logger.error("Gemini generation failed: %s", exc)
                return f"回答の生成中にエラーが発生しました: {exc}"
            if attempt >= _GEMINI_MAX_RETRIES - 1:
                logger.error("Gemini generation failed after retries: %s", exc)
                return (
                    "回答の生成中にエラーが発生しました（API の利用上限に達しています）。\n"
                    f"詳細: {exc}\n"
                    "しばらく待ってから再実行するか、Google AI のプラン・課金・レート制限を確認してください。"
                )
            delay = min(120.0, _GEMINI_BASE_DELAY_S * (2**attempt))
            logger.warning(
                "Gemini rate limited (429), sleeping %.1fs before retry %d/%d",
                delay,
                attempt + 2,
                _GEMINI_MAX_RETRIES,
            )
            time.sleep(delay)
    return ""


_SYSTEM_PROMPT = """
あなたは社内文書検索アシスタントです。
以下の社内資料に基づいて、質問に正確かつ簡潔に日本語で回答してください。

【ルール】
- 提供された資料の内容のみを根拠にしてください。
- 資料に記載がない情報は「資料には記載がありません」と明示してください。
- 複数の資料を参照した場合は、それぞれの出典（ファイル名）を明記してください。
- 箇条書きや見出しを使い、読みやすい形式で回答してください。
""".strip()


@dataclass
class Answer:
    question: str
    answer: str
    sources: list[dict]   # [{name, path, site, similarity}]
    retrieved_count: int


def ask(
    question: str,
    site_name: str | None = None,
    top_k: int | None = None,
) -> Answer:
    """
    Retrieve relevant chunks and generate an answer using Gemini.

    Parameters
    ----------
    question  : user's natural language question
    site_name : restrict search to a specific site
    top_k     : number of chunks to retrieve
    """
    chunks = retrieve(question, site_name=site_name, top_k=top_k)

    if not chunks:
        return Answer(
            question=question,
            answer="関連する資料が見つかりませんでした。\n検索対象のサイトやキーワードを確認してください。",
            sources=[],
            retrieved_count=0,
        )

    context_parts: list[str] = []
    sources: list[dict] = []
    seen_files: set[str] = set()

    for chunk in chunks:
        meta = chunk.get("metadata", {})
        file_name = meta.get("name", "不明")
        context_parts.append(f"【ファイル: {file_name}】\n{chunk['text']}")
        if file_name not in seen_files:
            sources.append(
                {
                    "name": file_name,
                    "path": meta.get("path", ""),
                    "site": meta.get("site_name", ""),
                    "similarity": chunk.get("similarity", 0),
                }
            )
            seen_files.add(file_name)

    context = "\n\n---\n\n".join(context_parts)

    prompt = f"""{_SYSTEM_PROMPT}

【参照資料】
{context}

【質問】
{question}

【回答】
"""

    answer_text = generate_content_answer(prompt)

    return Answer(
        question=question,
        answer=answer_text,
        sources=sources,
        retrieved_count=len(chunks),
    )


def format_answer(answer: Answer) -> str:
    """Pretty-print an Answer for CLI output."""
    lines = [
        "=" * 60,
        f"Q: {answer.question}",
        "=" * 60,
        "",
        answer.answer,
        "",
        f"── 参照資料 ({answer.retrieved_count} チャンク) ──",
    ]
    for src in answer.sources:
        site = src.get("site", "")
        site_part = f"[{site}]  " if site else ""
        if src.get("similarity") is not None:
            lines.append(
                f"  • {src['name']}  "
                f"{site_part}"
                f"(関連度: {src['similarity']:.2%})"
            )
        elif src.get("rank") is not None:
            url = src.get("web_url", "")
            extra = f"  {url}" if url else ""
            lines.append(f"  • {src['name']}  (検索順位: {src['rank']}){extra}")
        else:
            lines.append(f"  • {src['name']}  {site_part}".rstrip())
    lines.append("=" * 60)
    return "\n".join(lines)
