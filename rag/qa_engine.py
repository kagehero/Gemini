"""
QA engine: build a Gemini prompt from retrieved chunks and generate an answer.
Uses the google-genai SDK (v1.x+).
"""

import logging
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

    client = _get_client()
    try:
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
        )
        answer_text = response.text
    except Exception as exc:
        logger.error("Gemini generation failed: %s", exc)
        answer_text = f"回答の生成中にエラーが発生しました: {exc}"

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
