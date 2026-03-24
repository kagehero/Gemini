"""
Hybrid QA: SharePoint Search → download only top-N files → Gemini.

Reuses Microsoft search index; downloads only a few MB per question.
No vector DB required — suitable for large tenants (e.g. 650GB) and PoC scope.
"""

import logging
import tempfile
from pathlib import Path, PurePosixPath

from google import genai

from config import settings
from processing.cleaner import clean
from processing.file_parser import parse_file
from rag.qa_engine import Answer, _SYSTEM_PROMPT
from sharepoint import graph_client as gc

logger = logging.getLogger(__name__)

_genai: genai.Client | None = None

# Graph の file.mimeType から拡張子を推定（ファイル名に拡張子がない場合がある）
_MIME_MAP = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.ms-powerpoint": ".pptx",
    "application/msword": ".docx",
    "text/plain": ".txt",
}


def _effective_ext(resource: dict) -> str:
    """File suffix from name, or inferred from file.mimeType."""
    name = resource.get("name", "")
    ext = PurePosixPath(name).suffix.lower()
    if ext in settings.SUPPORTED_EXTENSIONS:
        return ext
    raw = (resource.get("file") or {}).get("mimeType") or ""
    mime = raw.split(";")[0].strip().lower()
    if mime in _MIME_MAP:
        return _MIME_MAP[mime]
    if "pdf" in mime:
        return ".pdf"
    if "wordprocessingml" in mime:
        return ".docx"
    if "spreadsheetml" in mime:
        return ".xlsx"
    if "ms-excel" in mime:
        return ".xls"
    if "presentationml" in mime:
        return ".pptx"
    return ext


def _get_genai_client() -> genai.Client:
    global _genai
    if _genai is None:
        _genai = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _genai


def _merge_drive_hits(primary: list[dict], secondary: list[dict]) -> list[dict]:
    """Dedupe by item id; preserve order (drive search first, then Microsoft Search)."""
    seen: set[str] = set()
    out: list[dict] = []
    for r in primary + secondary:
        rid = r.get("id")
        if not rid or rid in seen:
            continue
        seen.add(rid)
        out.append(r)
    return out


def _is_downloadable_file(resource: dict) -> bool:
    if resource.get("folder"):
        return False
    if not resource.get("id"):
        return False
    ext = _effective_ext(resource)
    if ext not in settings.SUPPORTED_EXTENSIONS:
        return False
    size = resource.get("size") or 0
    if size and size > settings.MAX_FILE_SIZE_BYTES:
        return False
    return True


def _harvest_hybrid_context(
    hits: list[dict],
    *,
    top: int,
    budget: int,
    fallback_site_id: str | None,
    site_name: str | None,
    skip_ids: frozenset[str] | None = None,
) -> tuple[list[str], list[dict], int, int]:
    """
    Download / parse hits until ``top`` successes or budget exhausted.
    Returns (context_parts, sources, used_chars, successes).
    """
    context_parts: list[str] = []
    sources: list[dict] = []
    used_chars = 0
    successes = 0
    sk = skip_ids or frozenset()

    for rank, r in enumerate(hits, start=1):
        if successes >= top:
            break

        iid = r.get("id")
        if iid and iid in sk:
            continue

        name = r.get("name", "不明")
        mime = (r.get("file") or {}).get("mimeType", "")
        eff_ext = _effective_ext(r)

        if not _is_downloadable_file(r):
            logger.info(
                "Hybrid: skip name=%r ext=%s mime=%s (not a supported office/doc type)",
                name,
                eff_ext or PurePosixPath(name).suffix,
                mime,
            )
            continue

        if not iid:
            logger.info("Hybrid: skip (no id): %s", name)
            continue

        try:
            data = gc.download_drive_item_content(r, fallback_site_id=fallback_site_id)
        except Exception as exc:
            logger.warning("Hybrid: download failed %s: %s", name, exc)
            continue

        tmp: Path | None = None
        sfx = eff_ext if eff_ext in settings.SUPPORTED_EXTENSIONS else ".bin"
        try:
            with tempfile.NamedTemporaryFile(suffix=sfx, delete=False) as tf:
                tf.write(data)
                tmp = Path(tf.name)
            raw = parse_file(tmp)
            text = clean(raw)
        finally:
            if tmp is not None:
                tmp.unlink(missing_ok=True)

        if not text.strip():
            logger.info(
                "Hybrid: parsed empty text name=%r suffix=%s mime=%s "
                "(画像のみPDF・暗号化Office・保護ファイル等の可能性)",
                name,
                sfx,
                mime,
            )
            continue

        remaining = budget - used_chars
        if remaining <= 0:
            break
        if len(text) > remaining:
            text = text[: max(0, remaining - 20)] + "\n…（長いため省略）"

        context_parts.append(f"【ファイル: {name}】\n{text}")
        used_chars += len(text)
        successes += 1
        sources.append(
            {
                "name": name,
                "path": "",
                "site": site_name or "",
                "similarity": None,
                "rank": rank,
                "web_url": r.get("webUrl", ""),
            }
        )

    return context_parts, sources, used_chars, successes


def ask_hybrid(
    question: str,
    site_name: str | None = None,
    top_files: int | None = None,
) -> Answer:
    """
    1) Microsoft Graph search (driveItem)
    2) Download only top_files hits
    3) Parse text and send to Gemini
    """
    top = top_files or settings.HYBRID_TOP_FILES
    # Ask search for extra hits — many rows lack driveId or wrong type; we stop after `top` successes
    search_size = min(50, max(top * 5, 15))

    fallback_site_id: str | None = None
    if site_name:
        site = gc.get_site(site_name)
        if site:
            fallback_site_id = site.get("id")
        else:
            logger.warning("Hybrid: get_site(%s) failed — downloads may fail without siteId", site_name)

    hits: list[dict] = []
    # Drive /root/search has full driveId; Microsoft Search often returns more matches.
    # Merge both so a single bad hit (e.g. encrypted xls) does not block other files.
    if fallback_site_id:
        drive_hits = gc.search_site_drive_root(fallback_site_id, question, search_size)
        if drive_hits:
            logger.info("Hybrid: drive root search returned %d item(s)", len(drive_hits))
        ms_hits: list[dict] = []
        if site_name:
            ms_hits = gc.search_documents(question, site_path=site_name, top=search_size)
            if ms_hits:
                logger.info("Hybrid: Microsoft Search returned %d item(s) for site", len(ms_hits))
        hits = _merge_drive_hits(drive_hits, ms_hits)
        if hits:
            logger.info("Hybrid: merged unique hits: %d", len(hits))

    if not hits and site_name:
        hits = gc.search_documents(question, site_path=site_name, top=search_size)
        if not hits:
            logger.info("Hybrid: no M365 search hits for site — retrying tenant-wide")
            hits = gc.search_documents(question, top=search_size)
    elif not hits:
        hits = gc.search_documents(question, top=search_size)

    if not hits:
        return Answer(
            question=question,
            answer="SharePoint 検索で該当するファイルが見つかりませんでした。\n"
            "キーワードを変えるか、サイト名（--site）を確認してください。",
            sources=[],
            retrieved_count=0,
        )

    budget = settings.HYBRID_MAX_CONTEXT_CHARS
    context_parts, sources, used_chars0, _succ = _harvest_hybrid_context(
        hits,
        top=top,
        budget=budget,
        fallback_site_id=fallback_site_id,
        site_name=site_name,
    )

    # Site-scoped hits may be a single encrypted / empty file; try more candidates tenant-wide.
    if not context_parts and site_name and hits:
        first_ids = frozenset(x for x in (h.get("id") for h in hits) if x)
        tenant_hits = gc.search_documents(question, top=search_size)
        extra = [r for r in tenant_hits if r.get("id") and r.get("id") not in first_ids]
        if extra:
            logger.info(
                "Hybrid: no readable text from site hits — trying %d tenant-wide result(s)",
                len(extra),
            )
            c2, s2, _, _ = _harvest_hybrid_context(
                extra,
                top=top,
                budget=budget - used_chars0,
                fallback_site_id=None,
                site_name=None,
            )
            context_parts.extend(c2)
            sources.extend(s2)

    if not context_parts:
        hint = ""
        if hits:
            h0 = hits[0]
            hint = (
                f"\n\n[デバッグ] 先頭ヒット: name={h0.get('name')!r} "
                f"mime={(h0.get('file') or {}).get('mimeType')!r} "
                f"folder={bool(h0.get('folder'))} "
                f"推定拡張子={_effective_ext(h0)!r}"
            )
        return Answer(
            question=question,
            answer=(
                "検索結果はありましたが、対応形式のファイルの取得・読み取りに失敗しました。\n"
                "（PDF / Word / Excel / PowerPoint / テキスト、かつサイズ上限内）\n"
                "ターミナルに Hybrid: のログが出ていれば理由の参考になります。"
                + hint
            ),
            sources=[],
            retrieved_count=0,
        )

    context = "\n\n---\n\n".join(context_parts)
    prompt = f"""{_SYSTEM_PROMPT}

【参照資料（SharePoint 検索で選ばれた上位ファイルのみ）】
{context}

【質問】
{question}

【回答】
"""

    try:
        resp = _get_genai_client().models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
        )
        answer_text = resp.text
    except Exception as exc:
        logger.error("Hybrid Gemini failed: %s", exc)
        answer_text = f"回答の生成中にエラーが発生しました: {exc}"

    return Answer(
        question=question,
        answer=answer_text,
        sources=sources,
        retrieved_count=len(sources),
    )
