"""
Interactive CLI for querying the SharePoint AI search system.

Usage:
  # RAG (vector index required)
  python -m scripts.query --ask "質問"

  # Hybrid (recommended for large tenants — no full index)
  python -m scripts.query --hybrid --ask "質問" --site eco-action

  # Compare RAG vs SharePoint Search list
  python -m scripts.query --compare "〇〇プロジェクトの概要"
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.WARNING)


def run_query(
    question: str,
    site_name: str | None,
    top_k: int,
    hybrid: bool,
    hybrid_top: int,
) -> None:
    from rag.qa_engine import format_answer
    if hybrid:
        from rag.hybrid_qa import ask_hybrid
        answer = ask_hybrid(question, site_name=site_name, top_files=hybrid_top)
    else:
        from rag.qa_engine import ask
        answer = ask(question, site_name=site_name, top_k=top_k)
    print(format_answer(answer))


def run_compare(question: str) -> None:
    """Show Gemini RAG answer alongside SharePoint Search results."""
    from rag.qa_engine import ask, format_answer
    from sharepoint.graph_client import search_documents

    print("\n" + "=" * 60)
    print("【Gemini RAG（ベクトル検索）】")
    print("=" * 60)
    answer = ask(question)
    print(format_answer(answer))

    print("\n" + "=" * 60)
    print("【SharePoint Search ヒット一覧（参考）】")
    print("=" * 60)
    try:
        hits = search_documents(question, top=5)
        if hits:
            for i, hit in enumerate(hits, 1):
                name = hit.get("name", "不明")
                url = hit.get("webUrl", "")
                print(f"  {i}. {name}")
                if url:
                    print(f"     {url}")
        else:
            print("  結果なし")
    except Exception as exc:
        print(f"  SharePoint Search エラー: {exc}")
    print("=" * 60)


def interactive_mode(hybrid: bool, hybrid_top: int) -> None:
    from config import settings
    from storage.metadata_store import get_stats

    if hybrid:
        print("\n" + "=" * 60)
        print("  SharePoint × Gemini（ハイブリッド）")
        print("  検索 → 上位ファイルのみ取得 → AI回答（全件ダウンロード不要）")
        print(f"  取得ファイル数上限: {hybrid_top}")
        print("  (終了: q または Ctrl+C)")
        print("=" * 60 + "\n")
        site_filter = input(
            "サイト名（例: eco-action）※Enter=テナント全体で検索: "
        ).strip() or None
        print(f"\nサイト: {site_filter or '（テナント全体）'}\n")
    else:
        stats = get_stats()
        print("\n" + "=" * 60)
        print("  SharePoint × Gemini（RAG / ベクトル検索）")
        print(f"  インデックス: {stats['total_files']} ファイル / {stats['total_chunks']} チャンク")
        if stats["total_files"] == 0:
            print("  ⚠ インデックスが空です。--hybrid の利用を検討してください。")
        print("  (終了: q または Ctrl+C)")
        print("=" * 60 + "\n")

        site_filter = None
        available_sites = list(stats.get("by_site", {}).keys())
        if available_sites:
            print("利用可能なサイト:")
            for i, s in enumerate(available_sites, 1):
                print(f"  [{i}] {s}")
            print("  [0] すべてのサイト")
            choice = input("\n検索サイトを選択 (Enter=すべて): ").strip()
            if choice.isdigit() and 0 < int(choice) <= len(available_sites):
                site_filter = available_sites[int(choice) - 1]

        print(f"\n検索対象: {'すべてのサイト' if not site_filter else site_filter}\n")

    while True:
        try:
            question = input("質問を入力 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n終了します。")
            break

        if question.lower() in ("q", "quit", "exit", ""):
            print("終了します。")
            break

        run_query(
            question,
            site_name=site_filter,
            top_k=settings.TOP_K,
            hybrid=hybrid,
            hybrid_top=hybrid_top,
        )
        print()


def main():
    parser = argparse.ArgumentParser(description="SharePoint Gemini AI Search")
    parser.add_argument("--ask", type=str, help="One-shot question")
    parser.add_argument("--site", type=str, default=None, help="Restrict to site name")
    parser.add_argument("--top-k", type=int, default=None, help="RAG: number of chunks")
    parser.add_argument(
        "--hybrid",
        action="store_true",
        help="Search→fetch top files→Gemini (no vector index; best for large tenants)",
    )
    parser.add_argument(
        "--hybrid-top",
        type=int,
        default=None,
        help="Hybrid: max files to download per question (default: HYBRID_TOP_FILES)",
    )
    parser.add_argument("--compare", type=str, help="Compare RAG vs SharePoint Search")
    args = parser.parse_args()

    from config import settings

    hybrid_top = args.hybrid_top or settings.HYBRID_TOP_FILES

    if args.compare:
        run_compare(args.compare)
    elif args.ask:
        run_query(
            args.ask,
            site_name=args.site,
            top_k=args.top_k or settings.TOP_K,
            hybrid=args.hybrid,
            hybrid_top=hybrid_top,
        )
    else:
        interactive_mode(hybrid=args.hybrid, hybrid_top=hybrid_top)


if __name__ == "__main__":
    main()
