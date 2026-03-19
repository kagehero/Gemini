"""
Connection test script — verify Graph API access and site availability.

Usage:
  python -m scripts.test_connection
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.WARNING)


def main():
    print("\n" + "=" * 60)
    print("  SharePoint × Gemini 接続テスト")
    print("=" * 60)

    # 1. Graph API token
    print("\n[1/4] Microsoft Graph API 認証テスト...")
    try:
        from auth.graph_auth import get_access_token
        token = get_access_token()
        print(f"  ✓ 認証成功 (token length: {len(token)})")
    except Exception as exc:
        print(f"  ✗ 認証失敗: {exc}")
        print("  → scripts.setup_azure_app を実行してください")
        sys.exit(1)

    # 2. SharePoint site access
    print("\n[2/4] SharePoint サイトアクセステスト...")
    from config import settings
    test_site = settings.PILOT_SITE or (settings.TARGET_SITES[0] if settings.TARGET_SITES else "")

    if not test_site:
        print("  ⚠ PILOT_SITE または TARGET_SITES が設定されていません")
    else:
        try:
            from sharepoint.graph_client import get_site, list_drives
            site = get_site(test_site)
            if site:
                print(f"  ✓ サイト取得成功: {site.get('displayName')} ({site.get('id')})")
                drives = list_drives(site["id"])
                print(f"  ✓ ドライブ数: {len(drives)}")
                for d in drives:
                    print(f"    - {d.get('name')} ({d.get('id')})")
            else:
                print(f"  ✗ サイトが見つかりません: {test_site}")
        except Exception as exc:
            print(f"  ✗ サイトアクセス失敗: {exc}")

    # 3. Gemini API
    print("\n[3/4] Gemini API テスト...")
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        result = client.models.embed_content(
            model=settings.GEMINI_EMBED_MODEL,
            contents=["接続テスト"],
            config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
        )
        dim = len(result.embeddings[0].values)
        print(f"  ✓ Embedding API 接続成功 (dimension: {dim})")
    except Exception as exc:
        print(f"  ✗ Gemini API 失敗: {exc}")
        print("  → .env の GEMINI_API_KEY を確認してください")

    # 4. Vector DB
    print("\n[4/4] Vector DB テスト...")
    try:
        from vector_db.vectordb import get_collection_stats
        stats = get_collection_stats()
        if stats:
            for col, count in stats.items():
                print(f"  ✓ Collection '{col}': {count} chunks")
        else:
            print("  ✓ Vector DB 接続成功 (インデックスはまだ空です)")
    except Exception as exc:
        print(f"  ✗ Vector DB エラー: {exc}")

    print("\n" + "=" * 60)
    print("  テスト完了")
    print("  次のステップ: python -m scripts.initial_index")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
