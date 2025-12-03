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
    list_documents,
    check_duplicate_document
)
from src.query_agent.agent import query_policy_documents
from src.utils.helpers import validate_file_extension, get_file_type
from src.evaluation.metrics import (
    RAGEvaluator,
    EvaluationSample,
    evaluate_single_query,
    get_evaluation_summary
)


# =============================================================================
# PYDANTIC MODELS FOR REQUEST/RESPONSE
# =============================================================================

class QueryRequest(BaseModel):
    """Request model for policy queries."""
    query: str = Field(..., description="The question to ask about policy documents")
    verbose: bool = Field(default=False, description="Include reasoning steps in response")
    document_ids: Optional[List[int]] = Field(default=None, description="Filter by specific document IDs (optional)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "What is the policy for requesting time off?",
                "verbose": False,
                "document_ids": None
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
# EVALUATION MODELS
# =============================================================================

class EvaluationRequest(BaseModel):
    """Request model for evaluating a RAG query result."""
    query: str = Field(..., description="The original question")
    answer: str = Field(..., description="The generated answer")
    contexts: List[str] = Field(..., description="The retrieved context chunks")
    ground_truth: Optional[str] = Field(None, description="Optional expected answer for recall calculation")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "What is NASA's policy on data management?",
                "answer": "NASA requires all data to be...",
                "contexts": ["Context chunk 1...", "Context chunk 2..."],
                "ground_truth": None
            }
        }


class EvaluationScores(BaseModel):
    """Individual evaluation scores."""
    faithfulness: float = Field(..., description="Does answer stick to context? (0-1)")
    answer_relevancy: float = Field(..., description="Does answer address question? (0-1)")
    context_precision: float = Field(..., description="How relevant is retrieved context? (0-1)")
    context_utilization: float = Field(..., description="How much context was used? (0-1)")
    completeness: float = Field(..., description="Is the answer complete? (0-1)")
    overall: float = Field(..., description="Weighted overall score (0-1)")


class EvaluationFeedback(BaseModel):
    """Detailed evaluation feedback."""
    faithfulness: str
    answer_relevancy: str
    context_precision: str
    context_utilization: str
    completeness: str
    hallucinations_detected: Optional[List[str]] = None
    missed_aspects: Optional[List[str]] = None
    irrelevant_chunks: Optional[List[int]] = None


class EvaluationResponse(BaseModel):
    """Response model for evaluation results."""
    query: str
    scores: EvaluationScores
    feedback: EvaluationFeedback
    summary: str
    timestamp: str
    status: str = "success"


class QueryAndEvaluateRequest(BaseModel):
    """Request model for combined query and evaluation."""
    query: str = Field(..., description="The question to ask about policy documents")
    document_ids: Optional[List[int]] = Field(None, description="Filter by specific document IDs")
    ground_truth: Optional[str] = Field(None, description="Optional expected answer for evaluation")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "What is NASA's policy on cybersecurity?",
                "document_ids": [1, 2],
                "ground_truth": None
            }
        }


class QueryAndEvaluateResponse(BaseModel):
    """Response model for combined query and evaluation."""
    query: str
    answer: str
    sources: List[dict]
    evaluation: EvaluationScores
    summary: str
    status: str


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
        409: {"model": ErrorResponse, "description": "Document already exists"},
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
    
    # Check for duplicate document
    existing_doc = check_duplicate_document(file.filename, file_size)
    if existing_doc:
        raise HTTPException(
            status_code=409,
            detail=f"Document already exists. Filename: '{existing_doc['filename']}' was uploaded on {existing_doc['created_at']} (Document ID: {existing_doc['id']})"
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
    Set `document_ids=[1,2,3]` to search only specific documents.
    """
    if not request.query.strip():
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty"
        )
    
    try:
        result = query_policy_documents(
            query=request.query,
            verbose=request.verbose,
            document_ids=request.document_ids
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
# RAG EVALUATION ENDPOINTS
# =============================================================================

@app.post(
    "/evaluate/offline",
    response_model=EvaluationResponse,
    tags=["Evaluation"],
    summary="[Offline] Evaluate pre-collected RAG results",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Evaluation failed"}
    }
)
async def evaluate_rag_result(request: EvaluationRequest):
    """
    [OFFLINE MODE] Evaluate pre-collected RAG query results.
    
    Use this endpoint when you have already run queries and collected the results.
    You provide the query, answer, and contexts - this endpoint only evaluates them.
    
    **Use cases:**
    - Batch evaluation of collected RAG results
    - A/B testing different prompts or configurations
    - Analyzing production logs
    - Creating benchmark test sets
    
    **Metrics evaluated:**
    - **Faithfulness**: Does the answer stick to the context? (detects hallucinations)
    - **Answer Relevancy**: Does the answer address the question?
    - **Context Precision**: How relevant was the retrieved context?
    - **Context Utilization**: How much of the context was used?
    - **Completeness**: Is the answer complete?
    
    Scores range from 0-1, higher is better.
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    if not request.answer.strip():
        raise HTTPException(status_code=400, detail="Answer cannot be empty")
    if not request.contexts:
        raise HTTPException(status_code=400, detail="At least one context chunk is required")
    
    try:
        # Run evaluation
        result = evaluate_single_query(
            query=request.query,
            contexts=request.contexts,
            answer=request.answer,
            ground_truth=request.ground_truth
        )
        
        # Generate summary
        summary = get_evaluation_summary(result)
        
        # Build response
        scores = EvaluationScores(
            faithfulness=result["scores"]["faithfulness"],
            answer_relevancy=result["scores"]["answer_relevancy"],
            context_precision=result["scores"]["context_precision"],
            context_utilization=result["scores"]["context_utilization"],
            completeness=result["scores"]["completeness"],
            overall=result["scores"]["overall"]
        )
        
        feedback = EvaluationFeedback(
            faithfulness=result["feedback"].get("faithfulness", ""),
            answer_relevancy=result["feedback"].get("answer_relevancy", ""),
            context_precision=result["feedback"].get("context_precision", ""),
            context_utilization=result["feedback"].get("context_utilization", ""),
            completeness=result["feedback"].get("completeness", ""),
            hallucinations_detected=result["feedback"].get("hallucinations_detected", []),
            missed_aspects=result["feedback"].get("missed_aspects", []),
            irrelevant_chunks=result["feedback"].get("irrelevant_chunks", [])
        )
        
        return EvaluationResponse(
            query=result["query"],
            scores=scores,
            feedback=feedback,
            summary=summary,
            timestamp=result["timestamp"],
            status="success"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Evaluation failed: {str(e)}"
        )


@app.post(
    "/evaluate/live",
    response_model=QueryAndEvaluateResponse,
    tags=["Evaluation"],
    summary="[Live] Query and evaluate end-to-end RAG pipeline",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Query or evaluation failed"}
    }
)
async def query_and_evaluate(request: QueryAndEvaluateRequest):
    """
    [LIVE MODE] Query the RAG pipeline and automatically evaluate the result.
    
    This is an end-to-end test endpoint that:
    1. Runs your query through the complete RAG pipeline (retrieval → generation)
    2. Automatically evaluates the quality of the result
    3. Returns both the answer and evaluation metrics
    
    **Use this for:**
    - Real-time testing of your RAG system
    - Monitoring production query quality
    - Identifying retrieval or generation issues
    - Performance benchmarking
    
    **Note:** This endpoint is slower than `/query` because it runs 5 additional 
    LLM calls for evaluation. Use `/query` for production and this for testing.
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    try:
        # Step 1: Run the query
        query_result = query_policy_documents(
            query=request.query,
            verbose=False,
            document_ids=request.document_ids
        )
        
        # Extract contexts from sources
        # The sources dict has "preview" field containing the text content
        contexts = [
            source.get("preview", "") or source.get("content", "")
            for source in query_result.get("sources", [])
            if source.get("preview") or source.get("content")
        ]
        
        if not contexts:
            raise HTTPException(
                status_code=400,
                detail="No context retrieved for evaluation"
            )
        
        # Step 2: Evaluate the result
        eval_result = evaluate_single_query(
            query=request.query,
            contexts=contexts,
            answer=query_result["answer"],
            ground_truth=request.ground_truth
        )
        
        # Build evaluation scores
        scores = EvaluationScores(
            faithfulness=eval_result["scores"]["faithfulness"],
            answer_relevancy=eval_result["scores"]["answer_relevancy"],
            context_precision=eval_result["scores"]["context_precision"],
            context_utilization=eval_result["scores"]["context_utilization"],
            completeness=eval_result["scores"]["completeness"],
            overall=eval_result["scores"]["overall"]
        )
        
        # Generate summary
        summary = get_evaluation_summary(eval_result)
        
        return QueryAndEvaluateResponse(
            query=query_result["query"],
            answer=query_result["answer"],
            sources=query_result["sources"],
            evaluation=scores,
            summary=summary,
            status="success"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Query and evaluation failed: {str(e)}"
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
            "evaluate-offline": "/evaluate/offline",
            "evaluate-live": "/evaluate/live",
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