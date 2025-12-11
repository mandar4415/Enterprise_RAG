"""
Configuration for Enterprise RAG - Simplified Edition
All settings in one place
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# LLM PROVIDERS (Priority: Groq > Gemini)
# Set API keys in .env file:
#   GROQ_API_KEY=your_key (14,400 req/day free)
#   GEMINI_API_KEY=your_key (1,500 req/day free - fallback)
# =============================================================================
LLM_TEMPERATURE = 0.0  # Deterministic responses for consistency

# Legacy: Keep for backward compatibility (not used with new llm.py)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY

# =============================================================================
# DATABASE
# =============================================================================
DATABASE_URL = os.getenv("DATABASE_URL", "")

# =============================================================================
# EMBEDDING MODEL (Nomic Embed v1.5 - Critical for quality)
# =============================================================================
EMBEDDING_MODEL = "nomic-ai/nomic-embed-text-v1.5"
EMBEDDING_DIM = 512  # Matryoshka dimension
EMBEDDING_PREFIX_DOC = "search_document: "
EMBEDDING_PREFIX_QUERY = "search_query: "

# =============================================================================
# RETRIEVAL & RERANKING (Critical for quality)
# =============================================================================
TOP_K_CANDIDATES = 20  # Initial retrieval (increased for multi-topic queries)
TOP_K_FINAL = 7  # After reranking (increased to cover multiple topics)
SIMILARITY_THRESHOLD = 0.3
MIN_RERANK_SCORE = -10.0  # Raw logit threshold (scores range -10 to +10, -10 allows all reasonable chunks)
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# =============================================================================
# METADATA FILTERING (Critical for quality)
# =============================================================================
FILTER_METADATA = True
METADATA_KEYWORDS = [
    "table of contents", "nodis library", "effective date",
    "expiration date", "compliance is mandatory", "index",
    "appendix", "revision history", "document control"
]

# =============================================================================
# CHUNKING (Simple character-based)
# =============================================================================
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# =============================================================================
# FILE UPLOAD
# =============================================================================
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB (increased for large documents)
MAX_QUERY_LENGTH = 2000  # Max query characters
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# =============================================================================
# AUTHENTICATION (Google OAuth + JWT)
# =============================================================================
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-secret-key-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

# =============================================================================
# EMAIL OTP (Gmail SMTP)
# =============================================================================
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
OTP_EXPIRE_MINUTES = int(os.getenv("OTP_EXPIRE_MINUTES", "10"))
OTP_LENGTH = 6  # 6-digit OTP
