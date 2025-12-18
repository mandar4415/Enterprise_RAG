"""
Authentication API routes.
Provides both Google OAuth and Email/Password with OTP verification.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field, EmailStr

from src.db import get_db
from src.auth.models import User, OTPCode
from src.auth.password import (
    hash_password, verify_password, validate_password,
    generate_otp, verify_otp, create_access_token
)
from src.auth.oauth import get_google_login_url, verify_google_token, is_google_oauth_configured
from src.auth.email import send_otp_email, is_smtp_configured
from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class SignupRequest(BaseModel):
    """Email signup request."""
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)


class LoginRequest(BaseModel):
    """Email login request."""
    email: EmailStr
    password: str


class VerifyOTPRequest(BaseModel):
    """OTP verification request."""
    email: EmailStr
    otp_code: str = Field(..., min_length=6, max_length=6)


class ResendOTPRequest(BaseModel):
    """Resend OTP request."""
    email: EmailStr


class TokenResponse(BaseModel):
    """Authentication token response."""
    access_token: str
    token_type: str = "bearer"
    user: dict


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str
    status: str = "success"


class UserResponse(BaseModel):
    """User profile response."""
    id: int
    email: str
    name: str
    auth_provider: str
    is_email_verified: bool
    profile_picture: Optional[str] = None
    created_at: str


# =============================================================================
# EMAIL/PASSWORD AUTHENTICATION ROUTES
# =============================================================================

@router.post("/signup", response_model=MessageResponse)
async def signup(request: SignupRequest):
    """
    Register a new user with email and password.
    Sends OTP to email for verification.
    """
    # Validate password strength
    is_valid, error = validate_password(request.password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)
    
    with get_db() as db:
        # Check if email already exists
        existing_user = db.query(User).filter(User.email == request.email).first()
        
        if existing_user:
            if existing_user.is_email_verified:
                raise HTTPException(status_code=409, detail="Email already registered")
            else:
                # User exists but not verified - resend OTP
                otp_code, expiry = generate_otp()
                
                # Create new OTP
                db.add(OTPCode(
                    user_id=existing_user.id,
                    code=otp_code,
                    purpose="signup",
                    expires_at=expiry
                ))
                db.commit()
                
                # Send email
                if is_smtp_configured():
                    success, error = send_otp_email(request.email, otp_code, "signup")
                    if not success:
                        raise HTTPException(status_code=500, detail=f"Failed to send OTP: {error}")
                
                return MessageResponse(
                    message=f"OTP sent to {request.email}. Please verify your email."
                )
        
        # Create new user
        user = User(
            email=request.email,
            name=request.name,
            password_hash=hash_password(request.password),
            auth_provider="email",
            is_email_verified=False
        )
        db.add(user)
        db.flush()
        
        # Generate OTP
        otp_code, expiry = generate_otp()
        
        db.add(OTPCode(
            user_id=user.id,
            code=otp_code,
            purpose="signup",
            expires_at=expiry
        ))
        db.commit()
        
        # Send OTP email
        if is_smtp_configured():
            success, error = send_otp_email(request.email, otp_code, "signup")
            if not success:
                raise HTTPException(status_code=500, detail=f"Failed to send OTP: {error}")
        else:
            # For development without SMTP
            print(f"[DEV] OTP for {request.email}: {otp_code}")
        
        return MessageResponse(
            message=f"OTP sent to {request.email}. Please verify your email."
        )


@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp_endpoint(request: VerifyOTPRequest):
    """
    Verify OTP code and complete email verification.
    Returns access token on success.
    """
    with get_db() as db:
        # Find user
        user = db.query(User).filter(User.email == request.email).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Find latest valid OTP
        otp = db.query(OTPCode).filter(
            OTPCode.user_id == user.id,
            OTPCode.purpose == "signup",
            OTPCode.is_used == False
        ).order_by(OTPCode.created_at.desc()).first()
        
        if not otp:
            raise HTTPException(status_code=400, detail="No valid OTP found. Please request a new one.")
        
        # Verify OTP
        is_valid, error = verify_otp(otp.code, request.otp_code, otp.expires_at, otp.is_used)
        
        if not is_valid:
            raise HTTPException(status_code=400, detail=error)
        
        # Mark OTP as used
        otp.is_used = True
        
        # Verify user email
        user.is_email_verified = True
        user.last_login = datetime.utcnow()
        
        db.commit()
        
        # Create access token
        access_token = create_access_token(data={"sub": str(user.id)})
        
        return TokenResponse(
            access_token=access_token,
            user={
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "auth_provider": user.auth_provider,
                "is_email_verified": user.is_email_verified
            }
        )


@router.post("/resend-otp", response_model=MessageResponse)
async def resend_otp(request: ResendOTPRequest):
    """Resend OTP to email."""
    with get_db() as db:
        user = db.query(User).filter(User.email == request.email).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if user.is_email_verified:
            raise HTTPException(status_code=400, detail="Email already verified")
        
        # Generate new OTP
        otp_code, expiry = generate_otp()
        
        db.add(OTPCode(
            user_id=user.id,
            code=otp_code,
            purpose="signup",
            expires_at=expiry
        ))
        db.commit()
        
        # Send OTP email
        if is_smtp_configured():
            success, error = send_otp_email(request.email, otp_code, "signup")
            if not success:
                raise HTTPException(status_code=500, detail=f"Failed to send OTP: {error}")
        else:
            print(f"[DEV] OTP for {request.email}: {otp_code}")
        
        return MessageResponse(message=f"New OTP sent to {request.email}")


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """
    Login with email and password.
    Only works for verified accounts.
    """
    with get_db() as db:
        user = db.query(User).filter(User.email == request.email).first()
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        if user.auth_provider != "email":
            raise HTTPException(
                status_code=400,
                detail=f"This account uses {user.auth_provider} login. Please use that method."
            )
        
        if not user.password_hash:
            raise HTTPException(status_code=400, detail="No password set for this account")
        
        if not verify_password(request.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        if not user.is_email_verified:
            raise HTTPException(
                status_code=403,
                detail="Email not verified. Please verify your email first."
            )
        
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account is deactivated")
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.commit()
        
        # Create access token
        access_token = create_access_token(data={"sub": str(user.id)})
        
        return TokenResponse(
            access_token=access_token,
            user={
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "auth_provider": user.auth_provider,
                "is_email_verified": user.is_email_verified,
                "profile_picture": user.profile_picture
            }
        )


# =============================================================================
# GOOGLE OAUTH ROUTES
# =============================================================================

@router.get("/google/login")
async def google_login():
    """
    Get Google OAuth login URL.
    Redirect user to this URL to initiate Google login.
    """
    if not is_google_oauth_configured():
        raise HTTPException(
            status_code=501,
            detail="Google OAuth not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
        )
    
    login_url = get_google_login_url()
    return {"login_url": login_url}


@router.get("/google/callback", response_model=TokenResponse)
async def google_callback(code: str = Query(...)):
    """
    Handle Google OAuth callback.
    Exchange authorization code for user info and create/login user.
    """
    if not is_google_oauth_configured():
        raise HTTPException(status_code=501, detail="Google OAuth not configured")
    
    # Verify Google token and get user info
    google_user = await verify_google_token(code)
    
    if not google_user:
        raise HTTPException(status_code=400, detail="Failed to verify Google authentication")
    
    if not google_user.verified_email:
        raise HTTPException(status_code=400, detail="Google email not verified")
    
    with get_db() as db:
        # Check if user exists by Google ID or email
        user = db.query(User).filter(
            (User.google_id == google_user.id) | (User.email == google_user.email)
        ).first()
        
        if user:
            # Existing user - update Google info if needed
            if not user.google_id:
                user.google_id = google_user.id
                user.auth_provider = "google"
            
            user.profile_picture = google_user.picture
            user.last_login = datetime.utcnow()
            user.is_email_verified = True  # Google already verified
            
        else:
            # New user - create account
            user = User(
                email=google_user.email,
                name=google_user.name,
                google_id=google_user.id,
                auth_provider="google",
                is_email_verified=True,  # Google already verified
                profile_picture=google_user.picture
            )
            db.add(user)
        
        db.commit()
        db.refresh(user)
        
        # Create access token
        access_token = create_access_token(data={"sub": str(user.id)})
        
        return TokenResponse(
            access_token=access_token,
            user={
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "auth_provider": user.auth_provider,
                "is_email_verified": user.is_email_verified,
                "profile_picture": user.profile_picture
            }
        )


# =============================================================================
# USER PROFILE ROUTES
# =============================================================================

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(user: User = Depends(get_current_user)):
    """Get current user's profile."""
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        auth_provider=user.auth_provider,
        is_email_verified=user.is_email_verified,
        profile_picture=user.profile_picture,
        created_at=user.created_at.isoformat()
    )


@router.get("/status")
async def auth_status():
    """Check authentication configuration status."""
    return {
        "google_oauth": is_google_oauth_configured(),
        "smtp_email": is_smtp_configured(),
        "status": "ready" if (is_google_oauth_configured() or is_smtp_configured()) else "needs_configuration"
    }
