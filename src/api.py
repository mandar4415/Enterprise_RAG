"""
FastAPI Application for Enterprise RAG - Simplified Edition
Clean API with authentication (Google OAuth + Email OTP + JWT)
"""
import os
from typing import Optional, List
from datetime import datetime

from fastapi import FastAPI, File, UploadFile, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from pydantic import BaseModel, Field

from src.config import ALLOWED_EXTENSIONS, MAX_FILE_SIZE, UPLOAD_DIR, JWT_SECRET_KEY
from src.db import init_db, check_db
from src.rag import query, ingest_document, list_documents, get_document, delete_document, check_duplicate
from src.evaluation import evaluate, get_summary
from src.auth import (
    oauth, create_access_token, get_or_create_google_user, get_or_create_email_user,
    get_current_user, require_auth, TokenResponse, UserResponse,
    EmailRequest, OTPVerifyRequest, MessageResponse,
    create_otp, send_otp_email, verify_otp
)


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
    # Evaluation metrics (computed server-side)
    answer_relevancy: Optional[float] = None
    overall: Optional[float] = None
    summary: Optional[str] = None
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
    llm_provider: str
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
    description="Policy document query system with Google OAuth authentication",
    version="2.0.0"
)

# IMPORTANT: Middleware order matters! Session must be added last (processed first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session middleware for OAuth state (must be after CORS to be processed first)
app.add_middleware(
    SessionMiddleware, 
    secret_key=JWT_SECRET_KEY,
    same_site="lax",  # Required for OAuth redirects
    https_only=False  # Set to True in production with HTTPS
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
    from src.llm import get_provider_name
    return HealthResponse(
        status="healthy",
        database="connected" if check_db() else "disconnected",
        llm_provider=get_provider_name(),
        timestamp=datetime.utcnow().isoformat()
    )


@app.get("/", tags=["System"])
async def root():
    """API info."""
    return {
        "name": "Enterprise RAG API",
        "version": "2.0.0 (With Authentication)",
        "endpoints": {
            "auth": {
                "google": ["/auth/google", "/auth/google/callback"],
                "email": ["/auth/email/send-otp", "/auth/email/verify-otp"],
                "user": ["/auth/me"]
            },
            "documents": ["/upload", "/documents", "/documents/{id}"],
            "query": ["/query", "/evaluate"],
            "system": ["/health"]
        }
    }


# =============================================================================
# AUTHENTICATION ENDPOINTS
# =============================================================================

# --- Google OAuth ---

@app.get("/auth/google", tags=["Authentication"])
async def google_login(request: Request):
    """
    Start Google OAuth login.
    Redirects to Google for authentication.
    """
    redirect_uri = request.url_for('google_callback')
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/google/callback", tags=["Authentication"])
async def google_callback(request: Request):
    """
    Google OAuth callback.
    Returns JWT token after successful authentication.
    """
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get('userinfo')
        
        if not user_info:
            raise HTTPException(400, "Failed to get user info from Google")
        
        # Get or create user in database
        user = get_or_create_google_user(user_info)
        
        # Create JWT token
        access_token, expires_in = create_access_token(user["id"], user["email"])
        
        # Return token (in production, you might redirect to frontend with token)
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in,
            user={
                "id": user["id"],
                "email": user["email"],
                "name": user["name"],
                "picture": user["picture"]
            }
        )
    except Exception as e:
        raise HTTPException(400, f"OAuth error: {str(e)}")


# --- Email OTP ---

@app.post("/auth/email/send-otp", response_model=MessageResponse, tags=["Authentication"])
async def send_otp(request: EmailRequest):
    """
    Send OTP to email for login/registration.
    Works for both new and existing users.
    """
    # Generate and store OTP
    otp = create_otp(request.email)
    
    # Send email
    if send_otp_email(request.email, otp):
        return MessageResponse(
            message=f"OTP sent to {request.email}. Check your inbox.",
            status="success"
        )
    else:
        raise HTTPException(500, "Failed to send OTP email. Please try again.")


@app.post("/auth/email/verify-otp", response_model=TokenResponse, tags=["Authentication"])
async def verify_otp_endpoint(request: OTPVerifyRequest):
    """
    Verify OTP and return JWT token.
    Creates user if doesn't exist (registration + login in one step).
    """
    # Verify OTP
    if not verify_otp(request.email, request.otp):
        raise HTTPException(400, "Invalid or expired OTP")
    
    # Get or create user
    user = get_or_create_email_user(request.email)
    
    # Create JWT token
    access_token, expires_in = create_access_token(user["id"], user["email"])
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        user={
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "picture": user.get("picture")
        }
    )


# --- User Info ---

@app.get("/auth/me", response_model=UserResponse, tags=["Authentication"])
async def get_me(user: dict = Depends(require_auth)):
    """Get current authenticated user info."""
    return UserResponse(
        id=user["id"],
        email=user["email"],
        name=user.get("name"),
        picture=user.get("picture"),
        auth_provider=user.get("auth_provider")
    )


# =============================================================================
# DOCUMENT ENDPOINTS
# =============================================================================

@app.post("/upload", response_model=DocumentResponse, tags=["Documents"])
async def upload(
    file: UploadFile = File(...),
    title: Optional[str] = Query(None),
    description: Optional[str] = Query(None),
    user: dict = Depends(require_auth)  # Require authentication
):
    """Upload a policy document (requires authentication)."""
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
    
    # Check duplicate for this user
    existing = check_duplicate(file.filename, len(content), user["id"])
    if existing:
        raise HTTPException(409, f"Document already exists (ID: {existing['id']})")
    
    # Save and ingest
    path = UPLOAD_DIR / file.filename
    try:
        path.write_bytes(content)
        result = ingest_document(str(path), file.filename, len(content), title, description, user["id"])
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
async def list_docs(user: dict = Depends(require_auth)):
    """List user's documents (requires authentication)."""
    docs = list_documents(user["id"])
    return {"documents": docs, "total": len(docs)}


@app.get("/documents/{doc_id}", response_model=DocumentResponse, tags=["Documents"])
async def get_doc(doc_id: int, user: dict = Depends(require_auth)):
    """Get document by ID (requires authentication, user can only access own docs)."""
    doc = get_document(doc_id, user["id"])
    if not doc:
        raise HTTPException(404, f"Document {doc_id} not found")
    return DocumentResponse(**doc, status="success")


@app.delete("/documents/{doc_id}", tags=["Documents"])
async def delete_doc(doc_id: int, user: dict = Depends(require_auth)):
    """Delete document (requires authentication, user can only delete own docs)."""
    if not delete_document(doc_id, user["id"]):
        raise HTTPException(404, f"Document {doc_id} not found")
    return {"status": "success", "message": f"Document {doc_id} deleted"}


# =============================================================================
# QUERY ENDPOINTS
# =============================================================================

@app.post("/query", response_model=QueryResponse, tags=["Query"])
async def query_docs(request: QueryRequest, user: dict = Depends(require_auth)):
    """Query user's policy documents (requires authentication)."""
    if not request.query.strip():
        raise HTTPException(400, "Query cannot be empty")
    if len(request.query) > 2000:
        raise HTTPException(400, "Query too long. Max 2000 characters.")
    
    result = query(request.query, request.document_ids, user["id"])

    # Prepare base response
    response_payload = {
        "query": result.get("query"),
        "expanded_queries": result.get("expanded_queries"),
        "answer": result.get("answer"),
        "sources": result.get("sources", []),
        "status": result.get("status", "success")
    }

    # If we retrieved context, run evaluation to compute metrics (same as /evaluate)
    try:
        if response_payload["sources"]:
            contexts = [s.get("preview", "").replace("...", "") for s in response_payload["sources"]]
            eval_result = evaluate(request.query, response_payload["answer"], contexts)
            evaluation = eval_result.get("evaluation", {})
            response_payload["answer_relevancy"] = evaluation.get("answer_relevancy")
            response_payload["overall"] = evaluation.get("overall")
            response_payload["summary"] = get_summary(eval_result)
        else:
            response_payload["answer_relevancy"] = None
            response_payload["overall"] = None
            response_payload["summary"] = None
    except Exception:
        # If evaluation fails, don't block the user — return the answer without metrics
        response_payload["answer_relevancy"] = None
        response_payload["overall"] = None
        response_payload["summary"] = None

    return QueryResponse(**response_payload)


# =============================================================================
# EVALUATION ENDPOINTS
# =============================================================================

@app.post("/evaluate", response_model=EvaluationResponse, tags=["Evaluation"])
async def evaluate_query(request: QueryRequest, user: dict = Depends(require_auth)):
    """Query and evaluate RAG pipeline (requires authentication)."""
    if not request.query.strip():
        raise HTTPException(400, "Query cannot be empty")
    
    # Run query (includes query expansion)
    result = query(request.query, request.document_ids, user["id"])
    
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
