"""
=============================================================================
RAG FOUNDATIONS — The Structure That NEVER Changes
=============================================================================
From beginner to production, EVERY RAG system follows this SAME skeleton:

    1. LOAD document
    2. CHUNK it into pieces
    3. EMBED chunks into vectors (numbers)
    4. STORE vectors in a vector DB
    5. USER asks a question
    6. EMBED the question
    7. SEARCH vector DB for similar chunks
    8. GIVE chunks + question to LLM
    9. LLM GENERATES answer

This file teaches each step. Read → Edit → Run.
Run: python learn/01_rag_foundations.py

NOTE: This file uses NO external vector DB — just Python lists + numpy.
      This is intentional. Understand the math FIRST, then use libraries.
=============================================================================
"""

# ========================
# STEP 0: SETUP
# ========================
# pip install sentence-transformers numpy langchain-text-splitters langchain-groq

import numpy as np
from typing import List, Dict

# Uncomment when you have API key:
# import os
# os.environ["GROQ_API_KEY"] = "your-key-here"  # Get free at https://console.groq.com


# ========================
# STEP 1: THE DOCUMENT
# ========================
# In real apps: you'd read from PDF/DOCX. Here we use a simple string.

DOCUMENT = """
Company Leave Policy - 2026 Edition

Section 1: Annual Leave
All full-time employees are entitled to 21 days of paid annual leave per year.
Leave must be approved by your direct manager at least 5 working days in advance.
Unused leave can be carried forward up to a maximum of 5 days to the next year.
Leave beyond 5 days carry-forward will be forfeited on December 31st.

Section 2: Work From Home
Employees may work from home up to 2 days per week with manager approval.
Remote work requires a stable internet connection and availability during core hours (10 AM - 4 PM).
Certain roles designated as "on-site required" are not eligible for WFH.
WFH requests must be submitted via the HR portal by Monday of each week.

Section 3: Sick Leave
Employees are entitled to 12 days of paid sick leave per year.
A medical certificate is required for sick leave exceeding 2 consecutive days.
Unused sick leave does NOT carry forward to the next year.
Sick leave cannot be used as annual leave or vice versa.

Section 4: Overtime Policy
All overtime must be pre-approved by a department head.
Overtime is compensated at 1.5x the regular hourly rate for weekdays.
Weekend overtime is compensated at 2x the regular hourly rate.
Maximum overtime allowed is 20 hours per month per employee.
"""


# ========================
# STEP 2: CHUNKING
# ========================
# WHY: LLMs have limited context. We split docs into small pieces
#       so we only send RELEVANT pieces, not the entire document.
#
# THE PATTERN: This chunking logic is the SAME whether you have
#              1 document or 10,000 documents.

def chunk_text_simple(text: str, chunk_size: int = 200, overlap: int = 50) -> List[str]:
    """
    Basic chunking: split text into overlapping pieces.
    
    chunk_size = max characters per chunk
    overlap    = characters shared between consecutive chunks (prevents cutting sentences)
    
    TRY: Change chunk_size to 100 or 500 and see how results change.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:  # Skip empty chunks
            chunks.append(chunk)
        start += chunk_size - overlap  # Move forward, but overlap with previous
    return chunks


# PRODUCTION VERSION: LangChain's splitter is smarter — it splits at sentence/paragraph boundaries
def chunk_text_langchain(text: str, chunk_size: int = 200, overlap: int = 50) -> List[str]:
    """
    LangChain's RecursiveCharacterTextSplitter.
    Tries to split at: paragraphs → sentences → words → characters
    This is what YOUR project (src/rag.py) uses.
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""]  # Try these split points in order
    )
    return splitter.split_text(text)


# ========================
# STEP 3: EMBEDDINGS
# ========================
# WHY: Computers can't search by "meaning" with text alone.
#       Embeddings convert text → numbers that CAPTURE meaning.
#       Similar meaning = similar numbers.
#
# THE PATTERN: embed(text) → list of floats. ALWAYS the same interface.

class SimpleEmbedder:
    """
    Uses sentence-transformers to create embeddings.
    This is the SAME pattern as your project's src/embeddings.py
    
    ANY embedding model follows this structure:
        model.encode(texts) → numpy array of vectors
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        all-MiniLM-L6-v2: Small, fast, good for learning (384 dimensions)
        Your project uses: nomic-ai/nomic-embed-text-v1.5 (768 → 512 dims)
        
        TRY: Change model_name to "all-mpnet-base-v2" (768 dims, better quality)
        """
        from sentence_transformers import SentenceTransformer
        print(f"Loading embedding model: {model_name}...")
        self.model = SentenceTransformer(model_name)
        self.dim = self.model.get_sentence_embedding_dimension()
        print(f"Loaded! Dimension: {self.dim}")
    
    def embed(self, texts: List[str]) -> np.ndarray:
        """Convert list of texts to embeddings. Shape: (num_texts, dimension)"""
        return self.model.encode(texts, convert_to_numpy=True)
    
    def embed_single(self, text: str) -> np.ndarray:
        """Convert single text to embedding. Shape: (dimension,)"""
        return self.model.encode([text], convert_to_numpy=True)[0]


# ========================
# STEP 4: VECTOR STORE (from scratch!)
# ========================
# WHY: After embedding chunks, we need to STORE them and SEARCH them.
#       This is what pgvector/Pinecone/ChromaDB do internally.
#       Understanding the math = understanding ALL vector DBs.
#
# THE PATTERN: store(embedding, metadata) → search(query_embedding) → results

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """
    Cosine similarity: measures angle between two vectors.
    
    1.0  = identical direction (same meaning)
    0.0  = perpendicular (unrelated)
    -1.0 = opposite direction
    
    Formula: dot(a, b) / (||a|| * ||b||)
    
    THIS IS THE CORE MATH behind every vector database.
    """
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)  # Length of vector a
    norm_b = np.linalg.norm(b)  # Length of vector b
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return float(dot_product / (norm_a * norm_b))


class SimpleVectorStore:
    """
    A vector database in ~30 lines. No external DB needed.
    
    Real vector DBs (pgvector, Pinecone, ChromaDB, Weaviate) do the SAME thing
    but with optimizations (HNSW indexing, clustering, disk storage).
    
    The API is ALWAYS:
        store.add(embedding, metadata)
        store.search(query_embedding, top_k) → results
    """
    
    def __init__(self):
        self.embeddings: List[np.ndarray] = []  # The vectors
        self.documents: List[Dict] = []          # The metadata (text, source, etc.)
    
    def add(self, embedding: np.ndarray, metadata: Dict):
        """Store an embedding with its metadata."""
        self.embeddings.append(embedding)
        self.documents.append(metadata)
    
    def search(self, query_embedding: np.ndarray, top_k: int = 3) -> List[Dict]:
        """
        Find the top_k most similar documents to the query.
        
        This is a BRUTE FORCE search (checks every vector).
        Real DBs use HNSW or IVF indexes to make this O(log n) instead of O(n).
        """
        if not self.embeddings:
            return []
        
        # Calculate similarity with every stored vector
        scores = []
        for i, emb in enumerate(self.embeddings):
            sim = cosine_similarity(query_embedding, emb)
            scores.append((sim, i))
        
        # Sort by similarity (highest first)
        scores.sort(key=lambda x: x[0], reverse=True)
        
        # Return top_k results
        results = []
        for sim, idx in scores[:top_k]:
            result = {**self.documents[idx]}  # Copy metadata
            result["similarity_score"] = round(sim, 4)
            results.append(result)
        
        return results
    
    def __len__(self):
        return len(self.embeddings)


# ========================
# STEP 5: LLM (Answer Generation)
# ========================
# THE PATTERN: messages = [system_msg, human_msg] → llm.invoke(messages) → answer

def generate_answer_with_llm(query: str, context_chunks: List[Dict]) -> str:
    """
    Give retrieved chunks + question to LLM → get answer.
    
    To run this: set GROQ_API_KEY environment variable.
    If no API key: returns a mock answer so you can still test the pipeline.
    """
    # Format context
    context = "\n\n---\n\n".join([
        f"Source {i+1}: {chunk['content']}"
        for i, chunk in enumerate(context_chunks)
    ])
    
    try:
        from langchain_groq import ChatGroq
        from langchain_core.messages import SystemMessage, HumanMessage
        
        llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.0)
        
        messages = [
            SystemMessage(content=(
                "You are a helpful assistant. Answer ONLY using the provided context. "
                "If the answer is not in the context, say 'I don't have that information.' "
                "Cite which Source number you used."
            )),
            HumanMessage(content=f"Context:\n{context}\n\nQuestion: {query}")
        ]
        
        response = llm.invoke(messages)
        return response.content
        
    except Exception as e:
        # No API key? Return mock answer so pipeline still works
        return (
            f"[MOCK - Set GROQ_API_KEY to get real answers]\n"
            f"Based on {len(context_chunks)} retrieved chunks, "
            f"the answer to '{query}' would be generated here.\n"
            f"Top chunk: {context_chunks[0]['content'][:100]}..."
        )


# ========================
# STEP 6: THE COMPLETE RAG PIPELINE
# ========================
# THIS is the structure that NEVER changes. Memorize this flow.

def rag_pipeline(document: str, query: str, chunk_size: int = 200, top_k: int = 3):
    """
    The complete RAG pipeline. Every RAG system — from a toy demo to 
    production — follows this EXACT structure.
    
    1. Chunk the document
    2. Embed the chunks
    3. Store in vector DB
    4. Embed the query
    5. Search for similar chunks
    6. Generate answer with LLM
    
    TRY:
    - Change chunk_size (100, 300, 500) and see how results change
    - Change top_k (1, 3, 5, 10) and see how answers improve
    - Change the query to ask different questions
    """
    print("=" * 60)
    print(f"QUERY: {query}")
    print("=" * 60)
    
    # Step 1: Chunk
    print("\n📄 Step 1: Chunking document...")
    chunks = chunk_text_langchain(document, chunk_size=chunk_size, overlap=50)
    print(f"   Created {len(chunks)} chunks (size={chunk_size}, overlap=50)")
    for i, chunk in enumerate(chunks):
        print(f"   Chunk {i}: ({len(chunk)} chars) {chunk[:60]}...")
    
    # Step 2 & 3: Embed + Store
    print(f"\n🧮 Step 2: Embedding {len(chunks)} chunks...")
    embedder = SimpleEmbedder()
    store = SimpleVectorStore()
    
    for i, chunk in enumerate(chunks):
        embedding = embedder.embed_single(chunk)
        store.add(embedding, {"content": chunk, "chunk_index": i})
    print(f"   Stored {len(store)} vectors (dim={embedder.dim})")
    
    # Step 4 & 5: Embed query + Search
    print(f"\n🔍 Step 3: Searching for relevant chunks...")
    query_embedding = embedder.embed_single(query)
    results = store.search(query_embedding, top_k=top_k)
    
    print(f"   Found top {len(results)} chunks:")
    for r in results:
        print(f"   Score: {r['similarity_score']:.4f} | {r['content'][:70]}...")
    
    # Step 6: Generate
    print(f"\n🤖 Step 4: Generating answer...")
    answer = generate_answer_with_llm(query, results)
    
    print(f"\n{'=' * 60}")
    print(f"ANSWER:\n{answer}")
    print(f"{'=' * 60}")
    
    return {"query": query, "answer": answer, "sources": results}


# ========================
# RUN IT!
# ========================
if __name__ == "__main__":
    print("\n" + "🚀 " * 20)
    print("RAG FOUNDATIONS — Learn by running!\n")
    
    # TRY different queries:
    queries = [
        "How many days of annual leave do employees get?",
        "What is the work from home policy?",
        "How is overtime compensated?",
        # "Can I carry forward sick leave?"   # Uncomment and try!
        # "What is the meaning of life?"      # Try something NOT in the document!
    ]
    
    for q in queries:
        rag_pipeline(DOCUMENT, q, chunk_size=200, top_k=3)
        print("\n\n")
    
    # ========================
    # EXPERIMENTS TO TRY:
    # ========================
    # 1. Change chunk_size to 500 — fewer chunks, each has more context
    # 2. Change chunk_size to 100 — more chunks, each is more specific
    # 3. Change top_k to 1 — only use the BEST chunk
    # 4. Change top_k to 10 — use many chunks (may include irrelevant ones)
    # 5. Ask a question NOT in the document — see what happens
    # 6. Add your own text to DOCUMENT and query it
    # 7. Try the simple chunker vs langchain chunker — compare results
