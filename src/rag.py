"""
RAG Pipeline for Enterprise RAG - Simplified Edition
Simple: expand → retrieve → rerank → generate
Production-ready with query expansion for complex queries
"""
from typing import List, Dict, Any, Optional
import re
import json
import hashlib
from datetime import datetime, timedelta
from threading import Lock

from langchain_core.messages import SystemMessage, HumanMessage
from sqlalchemy.orm import Session


# =============================================================================
# QUERY CACHE - Avoid duplicate API calls for same queries
# =============================================================================

class QueryCache:
    """
    Simple TTL-based cache for query results.
    Caches per user+query to avoid duplicate LLM/embedding calls.
    """
    def __init__(self, ttl_minutes: int = 10, max_size: int = 100):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
        self._ttl = timedelta(minutes=ttl_minutes)
        self._max_size = max_size
    
    def _make_key(self, query: str, user_id: int, document_ids: List[int] = None) -> str:
        """Create cache key from query params."""
        doc_str = ",".join(map(str, sorted(document_ids or [])))
        raw = f"{user_id}:{query.lower().strip()}:{doc_str}"
        return hashlib.md5(raw.encode()).hexdigest()
    
    def get(self, query: str, user_id: int, document_ids: List[int] = None) -> Optional[Dict[str, Any]]:
        """Get cached result if exists and not expired."""
        key = self._make_key(query, user_id, document_ids)
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if datetime.utcnow() < entry["expires_at"]:
                    entry["result"]["_cached"] = True  # Mark as cached
                    return entry["result"]
                else:
                    del self._cache[key]  # Expired
        return None
    
    def set(self, query: str, user_id: int, result: Dict[str, Any], document_ids: List[int] = None):
        """Store result in cache."""
        key = self._make_key(query, user_id, document_ids)
        with self._lock:
            # Evict oldest if at capacity
            if len(self._cache) >= self._max_size:
                oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k]["expires_at"])
                del self._cache[oldest_key]
            
            self._cache[key] = {
                "result": result.copy(),
                "expires_at": datetime.utcnow() + self._ttl
            }
    
    def clear(self):
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()


# Global cache instance (10 minute TTL, max 100 entries)
_query_cache = QueryCache(ttl_minutes=10, max_size=100)

from src.config import (
    TOP_K_CANDIDATES, TOP_K_FINAL,
    SIMILARITY_THRESHOLD, FILTER_METADATA, METADATA_KEYWORDS,
    CHUNK_SIZE, CHUNK_OVERLAP
)
from src.llm import get_llm, invoke_with_retry, get_provider_name
from src.db import get_db, Document, Chunk
from src.embeddings import embedder
from src.reranker import reranker
from langchain_text_splitters import RecursiveCharacterTextSplitter


# =============================================================================
# QUERY EXPANSION - Handles complex queries, jargon, and long documents
# =============================================================================

EXPANSION_PROMPT = """You are a search query optimizer for a document retrieval system.

Given a user's question, generate optimized search queries to find ALL relevant information.

HANDLE THESE CASES:
1. **Abbreviations/Jargon**: Expand to full terms AND synonyms
   - "WFH policy" → ["work from home policy", "remote work guidelines", "telecommuting rules"]
   
2. **Multi-topic questions**: Generate separate queries for EACH topic
   - "vacation policy and overtime approval" → ["vacation leave policy", "overtime approval process"]
   
3. **Long documents**: Generate diverse phrasings to catch scattered info
   - "employee benefits" → ["employee benefits overview", "health insurance coverage", "retirement plan details"]

RULES:
- Return 1-4 search queries (1 for simple, up to 4 for complex multi-topic)
- Each query should be 3-8 words, focused and specific
- Include the original query terms plus expansions
- Focus on terms likely to appear in formal policy/procedure documents

USER QUESTION: {query}

Respond with ONLY a JSON array of search queries, nothing else.
Example: ["search query 1", "search query 2"]"""


def is_simple_query(query: str) -> bool:
    """
    Check if query is simple enough to skip expansion.
    Saves 1 LLM call for straightforward queries.
    """
    # Simple if: short, single topic, no conjunctions
    words = query.split()
    if len(words) <= 6:
        return True
    # Check for multi-topic indicators
    multi_topic_words = [' and ', ' also ', ' plus ', ' as well as ', ' along with ']
    if not any(w in query.lower() for w in multi_topic_words):
        return True
    return False


def expand_query(query: str, force_expand: bool = False) -> List[str]:
    """
    Expand user query into optimized search queries.
    Handles: abbreviations, multi-topic questions, and ensures coverage for long docs.
    
    Args:
        query: User's query
        force_expand: Force expansion even for simple queries
    
    Returns:
        List of 1-4 search queries optimized for retrieval
    """
    # Skip expansion for simple queries to save API calls
    if not force_expand and is_simple_query(query):
        return [query]
    
    try:
        # Use unified LLM with automatic retry and fallback
        messages = [HumanMessage(content=EXPANSION_PROMPT.format(query=query))]
        content = invoke_with_retry(messages, temperature=0.0)
        
        # Parse JSON response
        content = content.strip()
        # Handle markdown code blocks if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        
        queries = json.loads(content)
        
        # Validate and limit
        if isinstance(queries, list) and len(queries) > 0:
            # Always include original query as first search
            expanded = [query] + [q for q in queries[:3] if q.lower() != query.lower()]
            return expanded[:4]  # Max 4 queries
        
        return [query]
        
    except Exception as e:
        print(f"Query expansion failed, using original: {e}")
        return [query]


# =============================================================================
# TEXT PROCESSING
# =============================================================================

def extract_text(file_path: str) -> str:
    """Extract text from PDF, DOCX, or TXT files."""
    from pathlib import Path
    ext = Path(file_path).suffix.lower()
    
    if ext == ".pdf":
        from pypdf import PdfReader
        return "\n\n".join(p.extract_text() or "" for p in PdfReader(file_path).pages)
    elif ext == ".docx":
        from docx import Document as DocxDoc
        return "\n\n".join(p.text for p in DocxDoc(file_path).paragraphs if p.text.strip())
    elif ext == ".txt":
        return Path(file_path).read_text(encoding='utf-8')
    raise ValueError(f"Unsupported file type: {ext}")

def clean_text(text: str) -> str:
    """Clean text for storage."""
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()

def chunk_text(text: str) -> List[Dict[str, Any]]:
    """Split text into chunks using simple character-based splitting."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    chunks = splitter.split_text(text)
    return [{"content": c, "chunk_index": i} for i, c in enumerate(chunks)]

def is_metadata(text: str) -> bool:
    """Check if chunk is metadata/header content."""
    if not FILTER_METADATA:
        return False
    text_lower = text.lower()
    if any(kw in text_lower for kw in METADATA_KEYWORDS):
        return True
    if len(text.strip()) < 100:
        return True
    special_ratio = sum(1 for c in text if c in '|_-=[]{}()<>') / max(len(text), 1)
    return special_ratio > 0.15


# =============================================================================
# INGESTION
# =============================================================================

def ingest_document(file_path: str, filename: str, file_size: int, 
                    title: str = None, description: str = None, user_id: int = None) -> Dict[str, Any]:
    """Ingest a document: extract → chunk → embed → store."""
    # Extract and clean
    text = clean_text(extract_text(file_path))
    if not text:
        raise ValueError("No text content found")
    
    # Chunk
    chunks = chunk_text(text)
    
    # Generate embeddings
    contents = [c["content"] for c in chunks]
    embeddings = embedder.encode(contents, is_query=False)
    
    # Store
    with get_db() as db:
        doc = Document(
            filename=filename, file_type=filename.split('.')[-1],
            file_size=file_size, title=title or filename, description=description,
            user_id=user_id  # Associate with user
        )
        db.add(doc)
        db.flush()
        
        for chunk, emb in zip(chunks, embeddings):
            db.add(Chunk(
                document_id=doc.id, content=chunk["content"],
                chunk_index=chunk["chunk_index"], embedding=emb
            ))
        
        return {"document_id": doc.id, "filename": filename, "num_chunks": len(chunks),
                "title": title or filename, "status": "success"}


# =============================================================================
# RETRIEVAL - With Multi-Query Support
# =============================================================================

def retrieve_single(query: str, document_ids: List[int] = None, top_k: int = TOP_K_CANDIDATES, user_id: int = None) -> List[Dict[str, Any]]:
    """Retrieve chunks for a single query (internal use)."""
    query_emb = embedder.encode_single(query, is_query=True)
    
    with get_db() as db:
        # Vector search
        q = db.query(Chunk, Chunk.embedding.cosine_distance(query_emb).label('distance')).join(Document)
        
        # Filter by user_id (user can only search their own documents)
        if user_id:
            q = q.filter(Document.user_id == user_id)
        
        if document_ids:
            q = q.filter(Chunk.document_id.in_(document_ids))
        results = q.order_by('distance').limit(top_k).all()
        
        # Convert to dicts and filter
        chunks = []
        for chunk, dist in results:
            sim = 1 - dist
            if sim < SIMILARITY_THRESHOLD or is_metadata(chunk.content):
                continue
            chunks.append({
                "id": chunk.id, "document_id": chunk.document_id,
                "content": chunk.content, "chunk_index": chunk.chunk_index,
                "document_title": chunk.document.title,
                "similarity_score": sim
            })
    
    return chunks


def retrieve_with_queries(queries: List[str], original_query: str, document_ids: List[int] = None, 
                          top_k: int = TOP_K_FINAL, user_id: int = None) -> List[Dict[str, Any]]:
    """
    Retrieve and rerank chunks using pre-expanded queries.
    
    Args:
        queries: List of expanded search queries
        original_query: Original user query (used for reranking)
        document_ids: Optional document filter
        top_k: Number of final results
        user_id: User ID for filtering (user can only search their own documents)
    """
    # Retrieve chunks for each expanded query
    all_chunks = {}  # Use dict to dedupe by chunk ID
    for q in queries:
        chunks = retrieve_single(q, document_ids, TOP_K_CANDIDATES, user_id)
        for c in chunks:
            # Keep best similarity score if duplicate
            if c["id"] not in all_chunks or c["similarity_score"] > all_chunks[c["id"]]["similarity_score"]:
                all_chunks[c["id"]] = c
    
    # Convert back to list
    chunks = list(all_chunks.values())
    
    if not chunks:
        return []
    
    # Rerank ALL retrieved chunks using ORIGINAL query (most important step)
    # The reranker scores based on actual relevance to the user's original question
    return reranker.rerank(original_query, chunks, top_k)


def retrieve(query: str, document_ids: List[int] = None, top_k: int = TOP_K_FINAL) -> List[Dict[str, Any]]:
    """
    Simple retrieve without expansion (for backward compatibility).
    Use retrieve_with_queries() for production with expansion.
    """
    chunks = retrieve_single(query, document_ids, TOP_K_CANDIDATES)
    if not chunks:
        return []
    return reranker.rerank(query, chunks, top_k)


# =============================================================================
# GENERATION
# =============================================================================

SYSTEM_PROMPT = """You are an expert policy assistant.

RULES:
1. ONLY use information from the provided context
2. DO NOT add information from your general knowledge
3. Cite sources using (Source X) format
4. If information is missing, say "Based on the documents, I don't have information about [topic]"
5. Include ALL relevant details, requirements, and conditions from the context
6. List ALL numbered items or bullet points if present

IMPORTANT: Hallucinating information is a serious error."""

def generate(query: str, chunks: List[Dict[str, Any]]) -> str:
    """Generate answer from retrieved chunks with automatic fallback."""
    if not chunks:
        return "I couldn't find relevant information to answer your question."
    
    # Format context
    context = "\n---\n".join(
        f"[Source {i+1}: {c['document_title']} (relevance: {c.get('rerank_score', c.get('similarity_score', 0)):.2f})]\n{c['content']}"
        for i, c in enumerate(chunks)
    )
    
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Question: {query}\n\nContext:\n{context}\n\nProvide a comprehensive answer.")
    ]
    
    try:
        # Use unified LLM with automatic retry and fallback
        return invoke_with_retry(messages)
    except Exception as e:
        error_str = str(e).lower()
        if "429" in str(e) or "quota" in error_str:
            return "Error: API rate limit exceeded. Please try again in a few minutes."
        raise


# =============================================================================
# MAIN QUERY FUNCTION
# =============================================================================

def query(q: str, document_ids: List[int] = None, user_id: int = None, use_expansion: bool = True) -> Dict[str, Any]:
    """
    Main RAG query function.
    Flow: check cache → expand → retrieve → rerank → generate → cache result
    
    Args:
        q: User's query
        document_ids: Optional list of document IDs to search
        user_id: User ID for filtering (user can only search their own documents)
        use_expansion: Whether to use query expansion (default: True)
    """
    # Check cache first (saves LLM + embedding API calls for duplicate queries)
    if user_id:
        cached = _query_cache.get(q, user_id, document_ids)
        if cached:
            print(f"[Cache HIT] Query: {q[:50]}...")
            return cached
    
    try:
        # Expand query ONCE here (not inside retrieve to avoid duplicate LLM calls)
        expanded_queries = expand_query(q) if use_expansion else [q]

        # Retrieve with pre-expanded queries (pass user_id for filtering)
        chunks = retrieve_with_queries(expanded_queries, q, document_ids, TOP_K_FINAL, user_id)
        answer = generate(q, chunks)

        # Compute overall confidence score from reranked chunks
        if chunks:
            # Use the top rerank_score as overall confidence
            top_score = chunks[0].get("rerank_score", chunks[0].get("similarity_score", 0))
        else:
            top_score = 0.0

        # Map score to friendly badge
        if top_score >= 0.75:
            confidence_badge = "High Confidence"
        elif top_score >= 0.5:
            confidence_badge = "Medium Confidence"
        elif top_score > 0.0:
            confidence_badge = "Low Confidence"
        else:
            confidence_badge = "No Confident Match"

        result = {
            "query": q,
            "answer": answer,
            "confidence_badge": confidence_badge,
            "status": "success"
        }

        # Cache result for future identical queries
        if user_id:
            _query_cache.set(q, user_id, result, document_ids)
            print(f"[Cache SET] Query: {q[:50]}...")

        return result
    except Exception as e:
        return {"query": q, "answer": f"Error: {str(e)}", "confidence_badge": "Error", "status": "error"}


# =============================================================================
# DOCUMENT MANAGEMENT
# =============================================================================

def list_documents(user_id: int = None) -> List[Dict[str, Any]]:
    """List documents (filtered by user_id if provided)."""
    with get_db() as db:
        q = db.query(Document)
        if user_id:
            q = q.filter(Document.user_id == user_id)
        docs = q.all()
        return [{"id": d.id, "filename": d.filename, "title": d.title,
                 "file_type": d.file_type, "file_size": d.file_size,
                 "num_chunks": len(d.chunks), "created_at": d.created_at.isoformat()} for d in docs]

def get_document(doc_id: int, user_id: int = None) -> Optional[Dict[str, Any]]:
    """Get document by ID (user can only access their own documents)."""
    with get_db() as db:
        q = db.query(Document).filter(Document.id == doc_id)
        if user_id:
            q = q.filter(Document.user_id == user_id)
        d = q.first()
        if not d:
            return None
        return {"id": d.id, "filename": d.filename, "title": d.title, "description": d.description,
                "file_type": d.file_type, "file_size": d.file_size, "num_chunks": len(d.chunks),
                "created_at": d.created_at.isoformat()}

def delete_document(doc_id: int, user_id: int = None) -> bool:
    """Delete document by ID (user can only delete their own documents)."""
    with get_db() as db:
        q = db.query(Document).filter(Document.id == doc_id)
        if user_id:
            q = q.filter(Document.user_id == user_id)
        d = q.first()
        if d:
            db.delete(d)
            return True
        return False

def check_duplicate(filename: str, file_size: int, user_id: int = None) -> Optional[Dict[str, Any]]:
    """Check if document already exists for this user."""
    with get_db() as db:
        q = db.query(Document).filter(Document.filename == filename, Document.file_size == file_size)
        if user_id:
            q = q.filter(Document.user_id == user_id)
        d = q.first()
        if d:
            return {"id": d.id, "filename": d.filename, "created_at": d.created_at.isoformat()}
        return None
