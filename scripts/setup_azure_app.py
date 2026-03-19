"""
Azure AD App Registration setup guide.

Run this script to get step-by-step instructions for creating
the required Azure AD App Registration for SharePoint API access.

Usage:
  python -m scripts.setup_azure_app
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


GUIDE = """
╔══════════════════════════════════════════════════════════════╗
║     Azure AD App Registration – セットアップガイド           ║
╚══════════════════════════════════════════════════════════════╝

SharePoint Graph API を使うには Azure AD にアプリを登録する必要があります。
以下の手順を実行してください。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 1: Azure Portal にログイン
  URL: https://portal.azure.com
  アカウント: dev_Partner02@mantan.co.jp (管理者権限が必要)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 2: アプリ登録
  1. 検索バーで「アプリの登録」を検索
  2. 「+ 新規登録」をクリック
  3. 入力:
     - 名前: SharePoint-Gemini-Search
     - サポートされるアカウントの種類: この組織のディレクトリのみ
     - リダイレクト URI: 空白のまま
  4. 「登録」をクリック

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 3: 必要情報を .env にコピー
  登録後の画面で以下を確認:
  ┌────────────────────────────────────────┐
  │ アプリケーション (クライアント) ID → CLIENT_ID  │
  │ ディレクトリ (テナント) ID → TENANT_ID        │
  └────────────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 4: API アクセス許可の追加
  左メニュー「APIのアクセス許可」→「アクセス許可の追加」
  → Microsoft Graph → アプリケーションの許可 を選択:

  必要な権限:
  ✓ Sites.Read.All       (SharePoint サイト読み取り)
  ✓ Files.Read.All       (ファイル読み取り)

  追加後:「<テナント名> に管理者の同意を与えます」をクリック

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ※ ユーザー委任 (デバイスコードフロー) を使う場合は:
  → 委任されたアクセス許可 を選択:
  ✓ Sites.Read.All
  ✓ Files.Read.All
  ✓ offline_access

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 5: クライアントシークレット作成 (アプリ権限の場合)
  左メニュー「証明書とシークレット」
  →「+ 新しいクライアントシークレット」
  →「追加」→ 値をすぐにコピー (再表示不可)
  → .env の CLIENT_SECRET に貼り付け

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 6: .env ファイルを更新
  cp .env.example .env
  # 以下を編集:
  TENANT_ID=xxxxxxxxxx
  CLIENT_ID=xxxxxxxxxx
  CLIENT_SECRET=xxxxxxxxxx  # アプリ権限の場合
  GEMINI_API_KEY=xxxxxxxxxx
  SHAREPOINT_HOSTNAME=ogakame001.sharepoint.com
  PILOT_SITE=SIOジャパン

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 7: 認証テスト
  python -m scripts.test_connection

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ℹ  クライアントシークレットなし（ユーザー認証）の場合:
   CLIENT_SECRET を空にすると、デバイスコードフロー (ブラウザ認証) が起動します。

"""


def main():
    print(GUIDE)


if __name__ == "__main__":
    main()
