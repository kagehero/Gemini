# SharePoint × Gemini AI Search

SharePoint上の業務ドキュメントをGemini AIで横断検索するシステムです。
Microsoft CopilotとGeminiの検索精度比較検証（PoC）を目的として構築しています。

## アーキテクチャ（2通り）

### 推奨: ハイブリッド（大容量テナント・PoC向け）

**全件ダウンロードや全件ベクトル化は不要。** SharePoint 既存の検索インデックスを使い、質問のたびに **上位数ファイルだけ** 取得して Gemini に渡します。

```
質問
  → Microsoft Graph search (driveItem)
  → 上位 N ファイルのみダウンロード・解析
  → Gemini 回答
```

```bash
.venv/bin/python main.py query --hybrid --ask "質問" --site eco-action
```

同一質問でハイブリッドとフル RAG を並べて比較する場合（RAG は事前に `main.py index --site …` が必要）:

```bash
.venv/bin/python -m scripts.compare_hybrid_rag --site eco-action --ask "質問"
```

環境変数: `HYBRID_TOP_FILES`（既定 5）、`HYBRID_MAX_CONTEXT_CHARS`（プロンプトに載せる文字上限）

**重要:** クライアント資格情報では **`GRAPH_SEARCH_REGION` が必須** です。サイト絞り込みは `contentSources` ではなく検索クエリ内の **KQL `Path:`** で行います（`driveItem` では `contentSources` が使えません）。

### オプション: フル RAG（ベクトル検索）

サイト単位で **クロール → 埋め込み → ChromaDB** し、オフラインに近い高速検索向け。

```
SharePoint
    │ Microsoft Graph API
    ▼ 並列ダウンロード
ドキュメント解析 → チャンク化 → Gemini Embedding → ChromaDB
    ▼
Retrieval + Gemini 回答
```

```bash
.venv/bin/python main.py index --site eco-action
.venv/bin/python main.py query --ask "質問"
```

## ディレクトリ構成

```
Geminni/
├── api/              FastAPI（Next.js から呼び出し）
├── web/              Next.js ブラウザ UI
├── config/           設定管理
├── auth/             Microsoft Graph API 認証
├── sharepoint/       SharePointクローラー・ダウンロード
├── processing/       ドキュメント解析・チャンク化
├── embedding/        Gemini Embeddingサービス
├── vector_db/        ChromaDBベクトルストア
├── storage/          SQLiteメタデータDB
├── rag/              Retrieval + Gemini QAエンジン
├── sync/             差分同期サービス
└── scripts/          実行スクリプト
```

## Web UI（Next.js）

日本語向けのシンプルな画面から、ハイブリッド / ベクトル RAG を切り替えて質問できます。

**ターミナル 1 — Python API**

```bash
.venv/bin/python main.py api
# または: .venv/bin/uvicorn api.app:app --reload --host 0.0.0.0 --port 8000
```

**ターミナル 2 — フロントエンド**

```bash
cd web
cp .env.local.example .env.local   # 必要なら API の URL を編集
npm install
npm run dev
```

ブラウザで **http://localhost:3000** を開きます。`.env` の `API_CORS_ORIGINS` にフロントのオリジン（既定 `http://localhost:3000`）が含まれていることを確認してください。

**Ubuntu VPS への本番デプロイ**（systemd・Nginx・HTTPS）は **[DEPLOY.md](./DEPLOY.md)** を参照してください。

## セットアップ

### 1. 依存パッケージのインストール

Ubuntu などでは `python` コマンドが無いことがあります。**プロジェクト直下で仮想環境を作り、その中に入れてください**（`ModuleNotFoundError: dotenv` はグローバルの `python3` を使っているときに起きます）。

```bash
cd /path/to/Geminni
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt
```

以降の実行は **`.venv/bin/python main.py ...`** とするか、`source .venv/bin/activate` してから `python main.py ...` としてください。

### 2. Azure AD アプリ登録

```bash
.venv/bin/python -m scripts.setup_azure_app
```

上記コマンドで表示される手順に従って Azure Portal でアプリを登録してください。

### 3. 環境変数の設定

```bash
cp .env.example .env
```

`.env` を編集:

```env
TENANT_ID=<AzureポータルのテナントID>
CLIENT_ID=<登録したアプリのクライアントID>
CLIENT_SECRET=<クライアントシークレット>
GEMINI_API_KEY=<Google AI StudioのAPIキー>
SHAREPOINT_HOSTNAME=ogakame001.sharepoint.com
PILOT_SITE=SIOジャパン
TARGET_SITES=SIOジャパン,TCS事業,海外事業部
```

### 4. 接続テスト

```bash
python main.py test
```

## 使い方

### 初期インデックス作成（初回のみ）

```bash
# パイロットサイト1つでテスト（推奨：まず小さいサイトで検証）
python main.py index

# 特定サイトを指定
python main.py index --site SIOジャパン

# 全サイト（650GB：時間がかかります）
python main.py index --all
```

### AI検索

```bash
# インタラクティブモード
python main.py query

# 1回の質問
python main.py query --ask "170周年プロジェクトの概要を教えて"

# 特定サイトに絞る
python main.py query --ask "2026年2月の実績報告" --site TCS事業

# Gemini vs SharePoint Search 比較（クライアントへの比較デモ用）
python main.py query --compare "プロジェクトの進捗をまとめて"
```

### 統計表示

```bash
python main.py stats
```

### 差分同期（毎日）

```bash
# 即時実行
python main.py sync --now

# デーモン起動（SYNC_TIME=02:00 に毎日実行）
python main.py sync --daemon
```

### cron 設定例（毎日02:00）

```cron
0 2 * * * cd /path/to/sharepoint_gemini_search && /path/to/venv/bin/python main.py sync --now >> /var/log/sp_sync.log 2>&1
```

## 実際のクエリ例（クライアント要件より）

```
# 170周年記念プロジェクトの進捗まとめ
python main.py query --ask "170周年記念プロジェクトの直近2ヶ月の進捗をまとめて"

# TCS事業部の前年比較
python main.py query --ask "TCS事業部の2026年2月の実績を前年同月と比較してまとめて" --site TCS事業

# 横断検索
python main.py query --ask "〇〇プロジェクトに関連する資料をまとめて"
```

## 段階的なインデックス拡張

650GBを一度に処理するのではなく、段階的に拡張することを推奨します。

| フェーズ | 対象 | 目的 |
|---------|------|------|
| Phase 1 | SIOジャパン (パイロット) | 動作確認・精度検証 |
| Phase 2 | + TCS事業, 海外事業部 | スケール検証 |
| Phase 3 | 全サイト | 本番運用 |

## ライセンス要件

| ライセンス | 月額 | 用途 |
|-----------|------|------|
| Microsoft 365 Business Standard | 既存 | SharePointアクセス |
| Microsoft Copilot | 既存 | 比較対象 |
| Gemini Enterprise | ~¥5,000 | AI検索 |
| Google AI Studio (API) | 従量 | Embedding + 生成 |

> **Note**: 小規模PoCでは Google AI Studio の無料枠内で収まる場合があります。
