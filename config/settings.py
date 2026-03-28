import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Microsoft Graph API ──────────────────────────────────────
TENANT_ID = os.getenv("TENANT_ID", "")
CLIENT_ID = os.getenv("CLIENT_ID", "")
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")
SP_USERNAME = os.getenv("SP_USERNAME", "")
SP_PASSWORD = os.getenv("SP_PASSWORD", "")

GRAPH_SCOPES = ["https://graph.microsoft.com/.default"]
GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
# アプリのみの Search API では region が必須（例: NAM, EUR, APC, JPN）
GRAPH_SEARCH_REGION = os.getenv("GRAPH_SEARCH_REGION", "APC").strip()

# ── SharePoint ───────────────────────────────────────────────
SHAREPOINT_HOSTNAME = os.getenv("SHAREPOINT_HOSTNAME", "ogakame001.sharepoint.com")
TARGET_SITES_RAW = os.getenv("TARGET_SITES", "")
TARGET_SITES = [s.strip() for s in TARGET_SITES_RAW.split(",") if s.strip()]
PILOT_SITE = os.getenv("PILOT_SITE", "")

# ── File Processing ──────────────────────────────────────────
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xls", ".pptx", ".txt"}
MAX_FILE_SIZE_BYTES = int(os.getenv("MAX_FILE_SIZE_MB", "50")) * 1024 * 1024
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))

# ── Gemini ───────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# 1.5 / 2.0 はキーによって 404（提供終了・新規不可）→ 2.5 を既定
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")
# gemini-embedding-001 の既定ベクトル次元（失敗時プレースホルダ用）
EMBED_DIMENSION = int(os.getenv("EMBED_DIMENSION", "3072"))
TOP_K = int(os.getenv("TOP_K", "5"))
# ベクトル RAG: コサイン類似度の下限（1 に近いほど厳しい）。0.75 固定だと日本語の自然文でヒットが 0 になりやすい。
RAG_MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "0.5"))

# ── Hybrid: Search → fetch → Gemini (no full download / no vector index) ──
HYBRID_TOP_FILES = int(os.getenv("HYBRID_TOP_FILES", "5"))
HYBRID_MAX_CONTEXT_CHARS = int(os.getenv("HYBRID_MAX_CONTEXT_CHARS", "120000"))

# ── Storage Paths ────────────────────────────────────────────
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
VECTOR_DB_DIR = Path(os.getenv("VECTOR_DB_DIR", "./data/vector_db"))
METADATA_DB_PATH = Path(os.getenv("METADATA_DB_PATH", "./data/metadata.db"))
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "./data/downloads"))
TOKEN_CACHE_PATH = Path(os.getenv("TOKEN_CACHE_PATH", "./data/token_cache.bin"))

for _p in [DATA_DIR, VECTOR_DB_DIR, DOWNLOAD_DIR]:
    _p.mkdir(parents=True, exist_ok=True)

# ── HTTP API (Next.js 等) ─────────────────────────────────────
# カンマ区切り: http://localhost:3000,http://127.0.0.1:3000
API_CORS_ORIGINS = [
    o.strip() for o in os.getenv("API_CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()
]
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# ── Performance ──────────────────────────────────────────────
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "10"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "50"))

# ── Sync ─────────────────────────────────────────────────────
SYNC_TIME = os.getenv("SYNC_TIME", "02:00")
DELTA_DAYS = int(os.getenv("DELTA_DAYS", "0"))
