"""
Interactive CLI for querying the SharePoint AI search system.

Usage:
  # Interactive mode
  python -m scripts.query

  # One-shot question
  python -m scripts.query --ask "170周年プロジェクトの概要を教えて"

  # Restrict to specific site
  python -m scripts.query --ask "進捗は？" --site TCS事業

  # Compare Gemini vs SharePoint Search (side-by-side)
  python -m scripts.query --compare "〇〇プロジェクトの概要"
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.WARNING)


def run_query(question: str, site_name: str | None, top_k: int) -> None:
    from rag.qa_engine import ask, format_answer
    answer = ask(question, site_name=site_name, top_k=top_k)
    print(format_answer(answer))


def run_compare(question: str) -> None:
    """Show Gemini RAG answer alongside SharePoint Search results."""
    from rag.qa_engine import ask, format_answer
    from sharepoint.graph_client import search_documents

    print("\n" + "=" * 60)
    print("【Gemini AI 検索結果】")
    print("=" * 60)
    answer = ask(question)
    print(format_answer(answer))

    print("\n" + "=" * 60)
    print("【SharePoint Search 結果 (参考)】")
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


def interactive_mode() -> None:
    from config import settings
    from storage.metadata_store import get_stats

    stats = get_stats()
    print("\n" + "=" * 60)
    print("  SharePoint × Gemini AI 検索")
    print(f"  インデックス: {stats['total_files']} ファイル / {stats['total_chunks']} チャンク")
    print("  (終了: 'q' または Ctrl+C)")
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

        run_query(question, site_name=site_filter, top_k=settings.TOP_K)
        print()


def main():
    parser = argparse.ArgumentParser(description="SharePoint Gemini AI Search")
    parser.add_argument("--ask", type=str, help="One-shot question")
    parser.add_argument("--site", type=str, default=None, help="Restrict to site name")
    parser.add_argument("--top-k", type=int, default=None, help="Number of chunks to retrieve")
    parser.add_argument("--compare", type=str, help="Compare Gemini vs SharePoint Search")
    args = parser.parse_args()

    if args.compare:
        run_compare(args.compare)
    elif args.ask:
        from config import settings
        run_query(args.ask, site_name=args.site, top_k=args.top_k or settings.TOP_K)
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
