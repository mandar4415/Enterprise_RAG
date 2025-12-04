"""
Configuration for Enterprise RAG - Simplified Edition
All settings in one place, ~50 lines
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# API KEYS
# =============================================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
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
# LLM
# =============================================================================
LLM_MODEL = "gemini-2.0-flash"
LLM_TEMPERATURE = 0.0

# =============================================================================
# CHUNKING (Simple character-based)
# =============================================================================
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# =============================================================================
# FILE UPLOAD
# =============================================================================
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
