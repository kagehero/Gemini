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

# ── SharePoint ───────────────────────────────────────────────
SHAREPOINT_HOSTNAME = os.getenv("SHAREPOINT_HOSTNAME", "ogakame001.sharepoint.com")
TARGET_SITES_RAW = os.getenv("TARGET_SITES", "")
TARGET_SITES = [s.strip() for s in TARGET_SITES_RAW.split(",") if s.strip()]
PILOT_SITE = os.getenv("PILOT_SITE", "")

# ── File Processing ──────────────────────────────────────────
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".pptx", ".txt"}
MAX_FILE_SIZE_BYTES = int(os.getenv("MAX_FILE_SIZE_MB", "50")) * 1024 * 1024
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))

# ── Gemini ───────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "models/text-embedding-004")
TOP_K = int(os.getenv("TOP_K", "5"))

# ── Storage Paths ────────────────────────────────────────────
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
VECTOR_DB_DIR = Path(os.getenv("VECTOR_DB_DIR", "./data/vector_db"))
METADATA_DB_PATH = Path(os.getenv("METADATA_DB_PATH", "./data/metadata.db"))
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "./data/downloads"))
TOKEN_CACHE_PATH = Path(os.getenv("TOKEN_CACHE_PATH", "./data/token_cache.bin"))

for _p in [DATA_DIR, VECTOR_DB_DIR, DOWNLOAD_DIR]:
    _p.mkdir(parents=True, exist_ok=True)

# ── Performance ──────────────────────────────────────────────
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "10"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "50"))

# ── Sync ─────────────────────────────────────────────────────
SYNC_TIME = os.getenv("SYNC_TIME", "02:00")
DELTA_DAYS = int(os.getenv("DELTA_DAYS", "0"))
