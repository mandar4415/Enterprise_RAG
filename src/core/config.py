"""
Configuration module for Deep Agent - Policy Edition
Contains all environment variables and settings for the application
"""
from dotenv import load_dotenv
import os
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# API KEYS
# =============================================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")  # Alias for langchain-google-genai

# Set the environment variable for langchain-google-genai
os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY or ""

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "deepagent")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# Full connection string
DATABASE_URL = os.getenv("DATABASE_URL")

# =============================================================================
# EMBEDDING MODEL CONFIGURATION
# =============================================================================
# Using sentence-transformers for local embeddings (free)
# all-MiniLM-L6-v2: 384 dimensions, fast, good quality for general use
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384  # Dimension size for all-MiniLM-L6-v2

# =============================================================================
# LLM CONFIGURATION  
# =============================================================================
# Using Google's Gemini model via langchain-google-genai
LLM_MODEL_NAME = "gemini-2.0-flash"  # Fast and capable model
LLM_TEMPERATURE = 0.0  # Low temperature for deterministic responses

# =============================================================================
# CHUNKING CONFIGURATION
# =============================================================================
# Optimized settings for policy documents
CHUNK_SIZE = 1000  # Characters per chunk
CHUNK_OVERLAP = 200  # Overlap between chunks for context continuity

# =============================================================================
# RETRIEVAL CONFIGURATION
# =============================================================================
# Number of documents to retrieve for each query
TOP_K_RESULTS = 5

# Number of initial candidates for re-ranking (retrieve more, then filter)
TOP_K_RERANK_CANDIDATES = 15

# Final number of chunks after re-ranking
TOP_K_AFTER_RERANK = 5

# Similarity threshold for relevance filtering (0.0 to 1.0)
# Chunks below this threshold will be filtered out
SIMILARITY_THRESHOLD = 0.3

# Minimum similarity score to be considered relevant (stricter filter)
MIN_RELEVANCE_SCORE = 0.4

# Enable re-ranking with cross-encoder
ENABLE_RERANKING = True

# =============================================================================
# FILE UPLOAD CONFIGURATION
# =============================================================================
# Allowed file extensions for document upload
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}

# Maximum file size in bytes (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024

# Temporary upload directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# =============================================================================
# AGENT CONFIGURATION
# =============================================================================
# Maximum number of correction attempts for Corrective RAG
MAX_CORRECTION_ATTEMPTS = 2

# Maximum steps for multi-step planning
MAX_PLANNING_STEPS = 5
