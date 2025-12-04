"""
FastAPI Application for Enterprise RAG - Simplified Edition
Clean API with 6 Pydantic models (~250 lines)
"""
import os
from typing import Optional, List
from datetime import datetime

from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.config import ALLOWED_EXTENSIONS, MAX_FILE_SIZE, UPLOAD_DIR
from src.db import init_db, check_db
from src.rag import query, ingest_document, list_documents, get_document, delete_document, check_duplicate
from src.evaluation import evaluate, get_summary


# =============================================================================
# PYDANTIC MODELS (6 total, down from 20+)
# =============================================================================

class QueryRequest(BaseModel):
    """Query request."""
    query: str = Field(..., description="Question about policies")
    document_ids: Optional[List[int]] = Field(None, description="Filter by document IDs")

class QueryResponse(BaseModel):
    """Query response."""
    query: str
    expanded_queries: Optional[List[str]] = None  # Shows what search queries were used
    answer: str
    sources: List[dict]
    status: str

class DocumentResponse(BaseModel):
    """Document response for upload/info."""
    id: Optional[int] = None
    filename: str
    title: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    num_chunks: Optional[int] = None
    created_at: Optional[str] = None
    status: str

class EvaluationResponse(BaseModel):
    """Evaluation response."""
    query: str
    expanded_queries: Optional[List[str]] = None
    answer: str
    sources: List[dict]
    evaluation: dict
    summary: str
    status: str

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    database: str
    timestamp: str

class ErrorResponse(BaseModel):
    """Error response."""
    detail: str
    status: str = "error"


# =============================================================================
# FASTAPI APP
# =============================================================================

app = FastAPI(
    title="Enterprise RAG API",
    description="Simplified policy document query system",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    """Initialize on startup."""
    print("Starting Enterprise RAG API v2...")
    if check_db():
        init_db()
        print("Database ready!")
    else:
        print("WARNING: Database connection failed")
    UPLOAD_DIR.mkdir(exist_ok=True)
    print("API ready!")


# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health():
    """Health check."""
    return HealthResponse(
        status="healthy",
        database="connected" if check_db() else "disconnected",
        timestamp=datetime.utcnow().isoformat()
    )


@app.get("/", tags=["System"])
async def root():
    """API info."""
    return {
        "name": "Enterprise RAG API",
        "version": "2.0.0 (Simplified)",
        "endpoints": ["/health", "/upload", "/query", "/documents", "/evaluate"]
    }


# =============================================================================
# DOCUMENT ENDPOINTS
# =============================================================================

@app.post("/upload", response_model=DocumentResponse, tags=["Documents"])
async def upload(
    file: UploadFile = File(...),
    title: Optional[str] = Query(None),
    description: Optional[str] = Query(None)
):
    """Upload a policy document."""
    # Validate extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type. Allowed: {ALLOWED_EXTENSIONS}")
    
    # Read and validate size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, f"File too large. Max: {MAX_FILE_SIZE // 1024 // 1024}MB")
    if len(content) == 0:
        raise HTTPException(400, "Empty file")
    
    # Check duplicate
    existing = check_duplicate(file.filename, len(content))
    if existing:
        raise HTTPException(409, f"Document already exists (ID: {existing['id']})")
    
    # Save and ingest
    path = UPLOAD_DIR / file.filename
    try:
        path.write_bytes(content)
        result = ingest_document(str(path), file.filename, len(content), title, description)
        return DocumentResponse(
            id=result["document_id"], filename=result["filename"],
            title=result["title"], num_chunks=result["num_chunks"], status="success"
        )
    except Exception as e:
        raise HTTPException(500, f"Ingestion failed: {str(e)}")
    finally:
        if path.exists():
            os.remove(path)


@app.get("/documents", tags=["Documents"])
async def list_docs():
    """List all documents."""
    docs = list_documents()
    return {"documents": docs, "total": len(docs)}


@app.get("/documents/{doc_id}", response_model=DocumentResponse, tags=["Documents"])
async def get_doc(doc_id: int):
    """Get document by ID."""
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(404, f"Document {doc_id} not found")
    return DocumentResponse(**doc, status="success")


@app.delete("/documents/{doc_id}", tags=["Documents"])
async def delete_doc(doc_id: int):
    """Delete document."""
    if not delete_document(doc_id):
        raise HTTPException(404, f"Document {doc_id} not found")
    return {"status": "success", "message": f"Document {doc_id} deleted"}


# =============================================================================
# QUERY ENDPOINTS
# =============================================================================

@app.post("/query", response_model=QueryResponse, tags=["Query"])
async def query_docs(request: QueryRequest):
    """Query policy documents."""
    if not request.query.strip():
        raise HTTPException(400, "Query cannot be empty")
    
    result = query(request.query, request.document_ids)
    return QueryResponse(**result)


# =============================================================================
# EVALUATION ENDPOINTS
# =============================================================================

@app.post("/evaluate", response_model=EvaluationResponse, tags=["Evaluation"])
async def evaluate_query(request: QueryRequest):
    """Query and evaluate RAG pipeline."""
    if not request.query.strip():
        raise HTTPException(400, "Query cannot be empty")
    
    # Run query (includes query expansion)
    result = query(request.query, request.document_ids)
    
    if result["status"] == "error" or not result["sources"]:
        raise HTTPException(400, "No context retrieved for evaluation")
    
    # Extract contexts
    contexts = [s.get("preview", "").replace("...", "") for s in result["sources"]]
    
    # Evaluate
    eval_result = evaluate(request.query, result["answer"], contexts)
    
    return EvaluationResponse(
        query=result["query"],
        expanded_queries=result.get("expanded_queries"),  # Include expanded queries
        answer=result["answer"],
        sources=result["sources"],
        evaluation=eval_result["evaluation"],
        summary=get_summary(eval_result),
        status="success"
    )


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api:app", host="0.0.0.0", port=8000, reload=True)
