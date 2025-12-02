"""
FastAPI Application for Deep Agent - Policy Edition
REST API endpoints for document ingestion and intelligent policy querying
"""
import os
import shutil
from typing import Optional, List
from datetime import datetime

from fastapi import FastAPI, File, UploadFile, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.core.config import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE,
    UPLOAD_DIR
)
from src.db.connection import init_db, check_connection, get_db
from src.ingestion.pipeline import (
    ingest_document,
    delete_document,
    get_document_info,
    list_documents
)
from src.query_agent.agent import query_policy_documents
from src.utils.helpers import validate_file_extension, get_file_type


# =============================================================================
# PYDANTIC MODELS FOR REQUEST/RESPONSE
# =============================================================================

class QueryRequest(BaseModel):
    """Request model for policy queries."""
    query: str = Field(..., description="The question to ask about policy documents")
    verbose: bool = Field(default=False, description="Include reasoning steps in response")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "What is the policy for requesting time off?",
                "verbose": False
            }
        }


class QueryResponse(BaseModel):
    """Response model for policy queries."""
    query: str
    answer: str
    sources: List[dict]
    status: str
    reasoning_steps: Optional[List[str]] = None


class DocumentResponse(BaseModel):
    """Response model for document operations."""
    document_id: int
    filename: str
    file_type: str
    file_size: int
    num_chunks: int
    title: str
    status: str


class DocumentInfo(BaseModel):
    """Model for document information."""
    id: int
    filename: str
    file_type: str
    file_size: int
    title: Optional[str]
    description: Optional[str] = None
    num_chunks: int
    created_at: str
    updated_at: Optional[str] = None


class DocumentListResponse(BaseModel):
    """Response model for listing documents."""
    documents: List[dict]
    total: int


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    database: str
    timestamp: str


class ErrorResponse(BaseModel):
    """Response model for errors."""
    detail: str
    status: str = "error"


# =============================================================================
# FASTAPI APPLICATION
# =============================================================================

app = FastAPI(
    title="Deep Agent - Policy Edition API",
    description="""
    Intelligent policy document query system using Agentic RAG.
    
    ## Features
    - **Document Upload**: Upload PDF, DOCX, or TXT policy documents
    - **Smart Querying**: Ask questions about policies using natural language
    - **Multi-Step Reasoning**: Complex queries are broken down automatically
    - **Corrective RAG**: Self-correcting retrieval for better accuracy
    
    ## Endpoints
    - `/upload` - Upload policy documents
    - `/query` - Query policy documents
    - `/documents` - List and manage documents
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# STARTUP EVENT
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    print("Starting Deep Agent - Policy Edition API...")
    
    # Check database connection
    if check_connection():
        print("Database connection successful")
        init_db()
        print("Database tables initialized")
    else:
        print("ERROR: Database connection failed - some features may not work")
    
    # Ensure upload directory exists
    UPLOAD_DIR.mkdir(exist_ok=True)
    print(f"Upload directory ready: {UPLOAD_DIR}")
    
    print("API ready to serve requests!")


# =============================================================================
# HEALTH CHECK ENDPOINT
# =============================================================================

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health check endpoint"
)
async def health_check():
    """Check the health status of the API and database connection."""
    db_status = "connected" if check_connection() else "disconnected"
    return HealthResponse(
        status="healthy",
        database=db_status,
        timestamp=datetime.utcnow().isoformat()
    )


# =============================================================================
# DOCUMENT UPLOAD ENDPOINT
# =============================================================================

@app.post(
    "/upload",
    response_model=DocumentResponse,
    tags=["Documents"],
    summary="Upload a policy document",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid file"},
        413: {"model": ErrorResponse, "description": "File too large"},
        500: {"model": ErrorResponse, "description": "Server error"}
    }
)
async def upload_document(
    file: UploadFile = File(..., description="Policy document to upload (PDF, DOCX, or TXT)"),
    title: Optional[str] = Query(None, description="Optional document title"),
    description: Optional[str] = Query(None, description="Optional document description")
):
    """
    Upload a policy document for ingestion.
    
    The document will be:
    1. Validated for file type and size
    2. Text extracted and cleaned
    3. Split into chunks
    4. Embedded and stored in the vector database
    
    Supported formats: PDF, DOCX, TXT
    Maximum file size: 10MB
    """
    # Validate file extension
    if not validate_file_extension(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Read file content to check size
    content = await file.read()
    file_size = len(content)
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE / (1024*1024):.1f}MB"
        )
    
    if file_size == 0:
        raise HTTPException(
            status_code=400,
            detail="Empty file uploaded"
        )
    
    # Save file temporarily
    temp_path = UPLOAD_DIR / file.filename
    try:
        with open(temp_path, "wb") as f:
            f.write(content)
        
        # Run ingestion pipeline
        result = ingest_document(
            file_path=str(temp_path),
            filename=file.filename,
            file_size=file_size,
            title=title,
            description=description
        )
        
        return DocumentResponse(
            document_id=result["document_id"],
            filename=result["filename"],
            file_type=result["file_type"],
            file_size=result["file_size"],
            num_chunks=result["num_chunks"],
            title=result["title"],
            status="success"
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")
    finally:
        # Clean up temporary file
        if temp_path.exists():
            os.remove(temp_path)


# =============================================================================
# QUERY ENDPOINT
# =============================================================================

@app.post(
    "/query",
    response_model=QueryResponse,
    tags=["Query"],
    summary="Query policy documents",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid query"},
        500: {"model": ErrorResponse, "description": "Server error"}
    }
)
async def query_documents(request: QueryRequest):
    """
    Query the policy documents using natural language.
    
    The system will:
    1. Analyze your query for complexity
    2. Break down complex queries into sub-questions if needed
    3. Search relevant policy documents
    4. Grade document relevance and rewrite queries if needed (Corrective RAG)
    5. Generate a comprehensive answer with source citations
    
    Set `verbose=true` to see the reasoning steps.
    """
    if not request.query.strip():
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty"
        )
    
    try:
        result = query_policy_documents(
            query=request.query,
            verbose=request.verbose
        )
        
        return QueryResponse(
            query=result["query"],
            answer=result["answer"],
            sources=result["sources"],
            status=result["status"],
            reasoning_steps=result.get("reasoning_steps")
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Query processing failed: {str(e)}"
        )


# =============================================================================
# DOCUMENT MANAGEMENT ENDPOINTS
# =============================================================================

@app.get(
    "/documents",
    response_model=DocumentListResponse,
    tags=["Documents"],
    summary="List all documents"
)
async def list_all_documents():
    """Get a list of all uploaded policy documents."""
    try:
        documents = list_documents()
        return DocumentListResponse(
            documents=documents,
            total=len(documents)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list documents: {str(e)}"
        )


@app.get(
    "/documents/{document_id}",
    response_model=DocumentInfo,
    tags=["Documents"],
    summary="Get document details"
)
async def get_document(document_id: int):
    """Get detailed information about a specific document."""
    try:
        doc_info = get_document_info(document_id)
        if not doc_info:
            raise HTTPException(
                status_code=404,
                detail=f"Document with ID {document_id} not found"
            )
        return DocumentInfo(**doc_info)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get document: {str(e)}"
        )


@app.delete(
    "/documents/{document_id}",
    tags=["Documents"],
    summary="Delete a document"
)
async def remove_document(document_id: int):
    """Delete a document and all its chunks from the database."""
    try:
        success = delete_document(document_id)
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Document with ID {document_id} not found"
            )
        return {"status": "success", "message": f"Document {document_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete document: {str(e)}"
        )


# =============================================================================
# ROOT ENDPOINT
# =============================================================================

@app.get("/", tags=["System"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Deep Agent - Policy Edition API",
        "version": "1.0.0",
        "description": "Intelligent policy document query system using Agentic RAG",
        "endpoints": {
            "health": "/health",
            "upload": "/upload",
            "query": "/query",
            "documents": "/documents",
            "docs": "/docs"
        }
    }


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )