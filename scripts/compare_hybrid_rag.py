"""
同一質問・同一サイトでハイブリッド検索とフル RAG の回答を並べて表示し、比較しやすくします。

  .venv/bin/python -m scripts.compare_hybrid_rag \\
    --site eco-action \\
    --ask "4月の請求書の内容を要約してください"

フル RAG は事前に `main.py index --site <SITE>` などでインデックスが必要です。
空の場合は警告を出してハイブリッドのみ意味のある比較になります。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare hybrid vs vector RAG answers")
    parser.add_argument("--site", type=str, required=True, help="SharePoint site path (e.g. eco-action)")
    parser.add_argument("--ask", type=str, required=True, help="Question text")
    parser.add_argument("--top-k", type=int, default=None, help="RAG: chunk count (default: TOP_K)")
    parser.add_argument(
        "--hybrid-top",
        type=int,
        default=None,
        help="Hybrid: max files per question (default: HYBRID_TOP_FILES)",
    )
    args = parser.parse_args()

    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
        datefmt="%H:%M:%S",
    )

    from config import settings
    from storage.metadata_store import get_stats, init_db
    from rag.qa_engine import format_answer, ask
    from rag.hybrid_qa import ask_hybrid

    init_db()
    stats = get_stats()

    top_k = args.top_k or settings.TOP_K
    hybrid_top = args.hybrid_top or settings.HYBRID_TOP_FILES

    print("\n" + "=" * 72)
    print("  比較条件")
    print("=" * 72)
    print(f"  サイト        : {args.site}")
    print(f"  質問          : {args.ask}")
    print(f"  RAG インデックス: {stats['total_files']} ファイル / {stats['total_chunks']} チャンク")
    site_files = stats.get("by_site", {}).get(args.site, 0)
    print(f"  そのうち {args.site}: {site_files} ファイル")
    if stats["total_chunks"] == 0:
        print("\n  ⚠ ベクトルインデックスが空です。RAG 側は「関連なし」になりがちです。")
        print("     先に: .venv/bin/python main.py index --site", args.site)
    elif site_files == 0:
        print(f"\n  ⚠ インデックスに「{args.site}」のファイルがありません。index --site {args.site} を実行してください。")
    print("=" * 72)

    print("\n" + "▼" * 24 + " 【A】ハイブリッド（Microsoft Search → 上位ファイル取得） " + "▼" * 24)
    ans_h = ask_hybrid(args.ask, site_name=args.site, top_files=hybrid_top)
    print(format_answer(ans_h))

    print("\n" + "▼" * 24 + " 【B】フル RAG（Chroma ベクトル検索 → チャンク取得） " + "▼" * 24)
    ans_r = ask(args.ask, site_name=args.site, top_k=top_k)
    print(format_answer(ans_r))

    print("\n" + "=" * 72)
    print("  精度比較の観点（例）")
    print("=" * 72)
    print("  • 参照資料のファイル名・URL が eco-action 配下か（意図したサイトか）")
    print("  • 請求書の実データに基づく要約か、それとも検索ミスによる別文書か")
    print("  • RAG: インデックス済み拡張子・パース可能なテキストのみが根拠になります")
    print("  • Hybrid: Microsoft Search の順位に依存；サイト 0 件時はテナント全体にフォールバックします")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    main()
